from __future__ import absolute_import

import uuid
from xml.etree import ElementTree
from couchdbkit.schema.properties import LazyDict
from django.template.loader import render_to_string
from casexml.apps.case.signals import process_cases, CaseProcessingConfig
from casexml.apps.phone.models import SyncLogAssertionError, SyncLog
from couchforms.models import XFormInstance
from couchforms.util import post_xform_to_couch
from dimagi.utils.parsing import json_format_datetime

def get_close_case_xml(time, case_id, uid=None):
    if not uid:
        uid = uuid.uuid4().hex
    time = json_format_datetime(time)
    return render_to_string("case/data/close.xml", locals())

def get_close_referral_xml(time, case_id, referral_id, referral_type, uid=None):
    if not uid:
        uid = uuid.uuid4().hex
    time = json_format_datetime(time)
    return render_to_string("case/data/close_referral.xml", locals())

def couchable_property(prop):
    """
    Sometimes properties that come from couch can't be put back in
    without some modification.
    """
    if isinstance(prop, LazyDict):
        return dict(prop)
    return prop

def post_case_blocks(case_blocks, form_extras=None):
    """
    Post case blocks.

    Extras is used to add runtime attributes to the form before
    sending it off to the case (current use case is sync-token pairing)
    """
    if form_extras is None:
        form_extras = {}
    form = ElementTree.Element("data")
    form.attrib['xmlns'] = "https://www.commcarehq.org/test/casexml-wrapper"
    form.attrib['xmlns:jrm'] ="http://openrosa.org/jr/xforms"
    for block in case_blocks:
        form.append(block)

    xform = post_xform_to_couch(ElementTree.tostring(form))
    for k, v in form_extras.items():
        setattr(xform, k, v)
    process_cases(sender="testharness", xform=xform)
    return xform


def reprocess_form_cases(form, config=None):
    """
    For a given form, reprocess all case elements inside it. This operation
    should be a no-op if the form was sucessfully processed, but should
    correctly inject the update into the case history if the form was NOT
    successfully processed.
    """
    process_cases(None, form, config)
    # mark cleaned up now that we've reprocessed it
    if form.doc_type != 'XFormInstance':
        form = XFormInstance.get(form._id)
        form.doc_type = 'XFormInstance'
        form.save()

def get_case_xform_ids(case_id):
    results = XFormInstance.get_db().view('case/form_case_index',
                                          reduce=False,
                                          startkey=[case_id],
                                          endkey=[case_id, {}])
    return list(set([row['key'][1] for row in results]))

def update_sync_log_with_checks(sync_log, xform, cases, case_id_blacklist=None):
    case_id_blacklist = case_id_blacklist or []
    try:
        sync_log.update_phone_lists(xform, cases)
    except SyncLogAssertionError, e:
        if e.case_id and e.case_id not in case_id_blacklist:
            form_ids = get_case_xform_ids(e.case_id)
            case_id_blacklist.append(e.case_id)
            for form_id in form_ids:
                if form_id != xform._id:
                    form = XFormInstance.get(form_id)
                    if form.doc_type in ['XFormInstance', 'XFormError']:
                        reprocess_form_cases(form, CaseProcessingConfig(strict_asserts=True,
                                                                        case_id_blacklist=case_id_blacklist))
            updated_log = SyncLog.get(sync_log._id)

            update_sync_log_with_checks(updated_log, xform, cases, case_id_blacklist=case_id_blacklist)