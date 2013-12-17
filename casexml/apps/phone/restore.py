import hashlib
from couchdbkit import ResourceConflict
from dimagi.utils.decorators.memoized import memoized
from casexml.apps.case.exceptions import BadStateException, RestoreException
from casexml.apps.phone.models import SyncLog, CaseState
import logging
from dimagi.utils.couch.database import get_db, get_safe_write_kwargs
from casexml.apps.phone import xml
from datetime import datetime
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache
from receiver.xml import get_response_element, get_simple_response_xml,\
    ResponseNature
from casexml.apps.case.xml import check_version, V1
from casexml.apps.phone.fixtures import generator
from django.http import HttpResponse
from casexml.apps.phone.checksum import CaseStateHash

class RestoreConfig(object):
    """
    A collection of attributes associated with an OTA restore
    """
    def __init__(self, user, restore_id="", version=V1, state_hash="", caching_enabled=False):
        self.user = user
        self.restore_id = restore_id
        self.version = version
        self.state_hash = state_hash
        self.caching_enabled = caching_enabled
        self.cache = get_redis_default_cache()

    @property
    @memoized
    def sync_log(self):
        return SyncLog.get(self.restore_id) if self.restore_id else None


    def validate(self):
        # runs validation checks, raises exceptions if anything is amiss
        check_version(self.version)
        if self.sync_log and self.state_hash:
            parsed_hash = CaseStateHash.parse(self.state_hash)
            if self.sync_log.get_state_hash() != parsed_hash:
                raise BadStateException(expected=self.sync_log.get_state_hash(),
                                        actual=parsed_hash,
                                        case_ids=self.sync_log.get_footprint_of_cases_on_phone())

    def get_commtrack_payload(self, syncop):
        # todo: fix this to not be badly dependent
        from corehq.apps.commtrack.processing import product_subcases

        cases = [e.case for e in syncop.actual_cases_to_sync]
        supply_points = [c for c in cases if c.type == 'supply-point']
        def product_entries():
            for sp in supply_points:
                spps = [spp.to_json() for spp in product_subcases(sp, create_new=False).values()]
                for spp in spps:
                    spp['supply_point'] = sp._id
                    yield spp

        from dimagi.utils.couch.loosechange import map_reduce
        product_by_supply_point = map_reduce(lambda e: [(e['supply_point'],)], data=product_entries(), include_docs=True)

        from lxml.builder import ElementMaker
        from corehq.apps.commtrack import const
        E = ElementMaker(namespace=const.COMMTRACK_REPORT_XMLNS)
        def mk_product(e):
            def _(attr, transform=lambda e: e):
                val = e.get(attr)
                return str(transform(val)) if val is not None else ''
            return E.product(
                id=_('product_id'),
                quantity=_('current_stock', int),
                consumption_rate=_('consumption'),
                stock_category=_('category'),
                stockout_since=_('stockout_since'),
            )
        for supply_point, products in product_by_supply_point.iteritems():
            product_last_reported_dates = filter(None, [p.get('last_reported', None) for p in products])
            if product_last_reported_dates:
                as_of = max(product_last_reported_dates)
                as_of = 'T'.join(as_of.split()) + 'Z' # FIXME convert to iso properly
            else:
                # todo: fix when there are no dates available
                as_of = ''
            yield E.balance(*(mk_product(e) for e in products), **{'entity-id': supply_point, 'date': as_of})

    def get_payload(self):
        user = self.user
        last_sync = self.sync_log

        self.validate()

        cached_payload = self.get_cached_payload()
        if cached_payload:
            return cached_payload

        sync_operation = user.get_case_updates(last_sync)
        case_xml_elements = [xml.get_case_element(op.case, op.required_updates, self.version)
                             for op in sync_operation.actual_cases_to_sync]
        commtrack_elements = self.get_commtrack_payload(sync_operation)

        last_seq = str(get_db().info()["update_seq"])

        # create a sync log for this
        previous_log_id = last_sync.get_id if last_sync else None

        synclog = SyncLog(user_id=user.user_id, last_seq=last_seq,
                          owner_ids_on_phone=user.get_owner_ids(),
                          date=datetime.utcnow(), previous_log_id=previous_log_id,
                          cases_on_phone=[CaseState.from_case(c) for c in \
                                          sync_operation.actual_owned_cases],
                          dependent_cases_on_phone=[CaseState.from_case(c) for c in \
                                                    sync_operation.actual_extended_cases])
        synclog.save(**get_safe_write_kwargs())

        # start with standard response
        response = get_response_element(
            "Successfully restored account %s!" % user.username,
            ResponseNature.OTA_RESTORE_SUCCESS)

        # add sync token info
        response.append(xml.get_sync_element(synclog.get_id))
        # registration block
        response.append(xml.get_registration_element(user))
        # fixture block
        for fixture in generator.get_fixtures(user, self.version, last_sync):
            response.append(fixture)
        # case blocks
        for case_elem in case_xml_elements:
            response.append(case_elem)
        for ct_elem in commtrack_elements:
            response.append(ct_elem)

        resp = xml.tostring(response)
        self.set_cached_payload_if_enabled(resp)
        return resp

    def get_response(self):
        try:
            return HttpResponse(self.get_payload(), mimetype="text/xml")
        except RestoreException, e:
            logging.exception("%s error during restore submitted by %s: %s" %
                              (type(e).__name__, self.user.username, str(e)))
            response = get_simple_response_xml(
                e.message,
                ResponseNature.OTA_RESTORE_ERROR
            )
            return HttpResponse(response, mimetype="text/xml",
                                status=412)  # precondition failed

    def _initial_cache_key(self):
        return hashlib.md5('ota-restore-{user}-{version}'.format(
            user=self.user.user_id,
            version=self.version,
        )).hexdigest()

    def get_cached_payload(self):
        if self.caching_enabled:
            if self.sync_log:
                return self.sync_log.get_cached_payload(self.version)
            else:
                return self.cache.get(self._initial_cache_key())

    def set_cached_payload_if_enabled(self, resp):
        if self.caching_enabled:
            if self.sync_log:
                try:
                    self.sync_log.set_cached_payload(resp, self.version)
                except ResourceConflict:
                    # if one sync takes a long time and another one updates the sync log
                    # this can fail. in this event, don't fail to respond, since it's just
                    # a caching optimization
                    pass
            else:
                self.cache.set(self._initial_cache_key(), resp, 60*60)


def generate_restore_payload(user, restore_id="", version=V1, state_hash=""):
    """
    Gets an XML payload suitable for OTA restore. If you need to do something
    other than find all cases matching user_id = user.user_id then you have
    to pass in a user object that overrides the get_case_updates() method.
    
    It should match the same signature as models.user.get_case_updates():
    
        user:          who the payload is for. must implement get_case_updates
        restore_id:    sync token
        version:       the CommCare version 
        
        returns: the xml payload of the sync operation
    """
    config = RestoreConfig(user, restore_id, version, state_hash)
    return config.get_payload()

def generate_restore_response(user, restore_id="", version="1.0", state_hash=""):
    return RestoreConfig(user, restore_id, version, state_hash).get_response()
