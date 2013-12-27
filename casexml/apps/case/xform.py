import logging

from couchdbkit.resource import ResourceNotFound
from casexml.apps.case.signals import cases_received
from couchforms.models import XFormInstance
from dimagi.utils.chunked import chunked
from casexml.apps.case.exceptions import IllegalCaseId, NoDomainProvided
from casexml.apps.case import settings
from dimagi.utils.couch.database import iter_docs

from casexml.apps.case import const
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml.parser import case_update_from_block
from casexml.apps.phone.models import SyncLog
from dimagi.utils.logging import notify_exception


def process_cases(xform, config=None):
    """
    Creates or updates case objects which live outside of the form.

    If reconcile is true it will perform an additional step of
    reconciling the case update history after the case is processed.
    """

    config = config or CaseProcessingConfig()
    cases = get_or_update_cases(xform).values()

    if config.reconcile:
        for c in cases:
            c.reconcile_actions(rebuild=True)

    # attach domain and export tag if domain is there
    if hasattr(xform, "domain"):
        domain = xform.domain

        def attach_extras(case):
            case.domain = domain
            if domain:
                assert hasattr(case, 'type')
                case['#export_tag'] = ["domain", "type"]
            return case

        cases = [attach_extras(case) for case in cases]

    # handle updating the sync records for apps that use sync mode

    last_sync_token = getattr(xform, 'last_sync_token', None)
    if last_sync_token:
        relevant_log = SyncLog.get(last_sync_token)
        # in reconciliation mode, things can be unexpected
        relevant_log.strict = config.strict_asserts
        from casexml.apps.case.util import update_sync_log_with_checks
        update_sync_log_with_checks(relevant_log, xform, cases,
                                    case_id_blacklist=config.case_id_blacklist)

        if config.reconcile:
            relevant_log.reconcile_cases()
            relevant_log.save()

    try:
        cases_received.send(sender=None, xform=xform, cases=cases)
    except Exception as e:
        # don't let the exceptions in signals prevent standard case processing
        notify_exception(
            None,
            'something went wrong sending the cases_received signal '
            'for form %s: %s' % (xform._id, e)
        )

    # set flags for indicator pillows and save
    xform.initial_processing_complete = True

    # if there are pillows or other _changes listeners competing to update
    # this form, override them. this will create a new entry in the feed
    # that they can re-pick up on
    xform.save(force_update=True)
    for case in cases:
        case.force_save()
    return cases


class CaseProcessingConfig(object):
    def __init__(self, reconcile=False, strict_asserts=True, case_id_blacklist=None):
        self.reconcile = reconcile
        self.strict_asserts = strict_asserts
        self.case_id_blacklist = case_id_blacklist or []

    def __repr__(self):
        return 'reconcile: {reconcile}, strict: {strict}, ids: {ids}'.format(
            reconcile=self.reconcile,
            strict=self.strict_asserts,
            ids=", ".join(self.case_id_blacklist)
        )


class CaseDbCache(object):
    """
    A temp object we use to keep a cache of in-memory cases around
    so we can get the latest updates even if they haven't been saved
    to the database. Also provides some type checking safety.
    """
    def __init__(self, domain=None, strip_history=False, deleted_ok=False):
        self.cache = {}
        self.domain = domain
        self.strip_history = strip_history
        self.deleted_ok = deleted_ok

    def validate_doc(self, doc):
        if self.domain and doc.domain != self.domain:
            raise IllegalCaseId("Bad case id")
        elif doc.doc_type == 'CommCareCase-Deleted':
            if not self.deleted_ok:
                raise IllegalCaseId("Case [%s] is deleted " % doc.get_id)
        elif doc.doc_type != 'CommCareCase':
            raise IllegalCaseId(
                "Bad case doc type! "
                "This usually means you are using a bad value for case_id."
            )

    def get(self, case_id):
        if case_id in self.cache:
            return self.cache[case_id]

        try: 
            case_doc = CommCareCase.get(case_id, strip_history=self.strip_history)
        except ResourceNotFound:
            return None

        self.validate_doc(case_doc)
        self.cache[case_id] = case_doc
        return case_doc
        
    def set(self, case_id, case):
        self.cache[case_id] = case
        
    def doc_exist(self, case_id):
        return case_id in self.cache or CommCareCase.get_db().doc_exist(case_id)

    def in_cache(self, case_id):
        return case_id in self.cache

    def populate(self, case_ids):

        def _iter_raw_cases(case_ids):
            if self.strip_history:
                for ids in chunked(case_ids, 100):
                    for row in CommCareCase.get_db().view("case/get_lite", keys=ids, include_docs=False):
                        yield row['value']
            else:
                for raw_case in iter_docs(CommCareCase.get_db(), case_ids):
                    yield raw_case

        for raw_case in  _iter_raw_cases(case_ids):
            case = CommCareCase.wrap(raw_case)
            self.set(case._id, case)


def get_and_check_xform_domain(xform):
    try:
        domain = xform.domain
    except AttributeError:
        domain = None

    if not domain and settings.CASEXML_FORCE_DOMAIN_CHECK:
        raise NoDomainProvided()

    return domain


def get_or_update_cases(xform):
    """
    Given an xform document, update any case blocks found within it,
    returning a dictionary mapping the case ids affected to the
    couch case document objects
    """
    case_blocks = extract_case_blocks(xform)

    domain = get_and_check_xform_domain(xform)

    case_db = CaseDbCache(domain=domain)
    for case_block in case_blocks:
        case_doc = _get_or_update_model(case_block, xform, case_db)
        if case_doc:
            # todo: legacy behavior, should remove after new case processing
            # is fully enabled.
            if xform._id not in case_doc.xform_ids:
                case_doc.xform_ids.append(xform.get_id)
            case_db.set(case_doc.case_id, case_doc)
        else:
            logging.error(
                "XForm %s had a case block that wasn't able to create a case! "
                "This usually means it had a missing ID" % xform.get_id
            )
    
    # once we've gotten through everything, validate all indices
    def _validate_indices(case):
        if case.indices:
            for index in case.indices:
                if not case_db.doc_exist(index.referenced_id):
                    raise Exception(
                        ("Submitted index against an unknown case id: %s. "
                         "This is not allowed. Most likely your case "
                         "database is corrupt and you should restore your "
                         "phone directly from the server.") % index.referenced_id)
    [_validate_indices(case) for case in case_db.cache.values()]
    return case_db.cache


def _get_or_update_model(case_block, xform, case_db):
    """
    Gets or updates an existing case, based on a block of data in a 
    submitted form.  Doesn't save anything.
    """
    
    case_update = case_update_from_block(case_block)
    case = case_db.get(case_update.id)
    
    if case is None:
        case = CommCareCase.from_case_update(case_update, xform)
        return case
    else:
        case.update_from_case_update(case_update, xform)
        return case


def is_device_report(doc):
    """exclude device reports"""
    device_report_xmlns = "http://code.javarosa.org/devicereport"
    return "@xmlns" in doc and doc["@xmlns"] == device_report_xmlns


def has_case_id(case_block):
    return const.CASE_TAG_ID in case_block or const.CASE_ATTR_ID in case_block


def extract_case_blocks(doc):
    """
    Extract all case blocks from a document, returning an array of dictionaries
    with the data in each case. 
    """

    if isinstance(doc, XFormInstance):
        doc = doc.form
    return list(_extract_case_blocks(doc))


def _extract_case_blocks(data):
    """
    helper for extract_case_blocks

    data must be json representing a node in an xform submission

    """
    if isinstance(data, list):
        for item in data:
            for case_block in _extract_case_blocks(item):
                yield case_block
    elif isinstance(data, dict) and not is_device_report(data):
        for key, value in data.items():
            if const.CASE_TAG == key:
                # it's a case block! Stop recursion and add to this value
                if isinstance(value, list):
                    case_blocks = value
                else:
                    case_blocks = [value]

                for case_block in case_blocks:
                    if has_case_id(case_block):
                        yield case_block
            else:
                for case_block in _extract_case_blocks(value):
                    yield case_block
    else:
        return


def get_case_updates(xform):
    return [case_update_from_block(cb) for cb in extract_case_blocks(xform)]


def get_case_ids_from_form(xform):
    return set(cu.id for cu in get_case_updates(xform))


def cases_referenced_by_xform(xform):
    """
    JSON repr of XFormInstance -> [CommCareCase]
    """
    case_ids = get_case_ids_from_form(xform)

    cases = [CommCareCase.wrap(doc)
             for doc in iter_docs(CommCareCase.get_db(), case_ids)]

    domain = get_and_check_xform_domain(xform)
    if domain:
        for case in cases:
            assert case.domain == domain

    return cases
