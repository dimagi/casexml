from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import get_case_xform_ids, doc_from_doc_or_id
from casexml.apps.case.xform import get_case_updates
from couchforms.models import get as get_form

def rebuild_case(case_or_case_id):
    """
    Given a case ID, rebuild the entire case state based on all existing forms
    referencing it. Useful when things go wrong or when you need to manually
    rebuild a case afer archiving / deliting it
    """
    case = doc_from_doc_or_id(case_or_case_id, CommCareCase)

    # clear actions, xform_ids, and close state
    # todo: properties too?
    case.doc_type = 'CommCareCase'
    case.xform_ids = []
    case.actions = []
    case.closed = False
    case.closed_on = None
    case.closed_by = ''

    form_ids = get_case_xform_ids(case._id)
    forms = [get_form(id) for id in form_ids]
    filtered_forms = [f for f in forms if f.doc_type == "XFormInstance"]
    sorted_forms = sorted(filtered_forms, key=lambda f: f.received_on)
    for form in sorted_forms:
        assert form.domain == case.domain
        case_updates = get_case_updates(form)
        filtered_updates = [u for u in case_updates if u.id == case._id]
        for u in filtered_updates:
            case.update_from_case_update(u, form)

    case.xform_ids = [f._id for f in sorted_forms]
    if not case.xform_ids:
        # there were no more forms. 'delete' the case
        case.doc_type = 'CommCareCase-Deleted'
    case.save()
    return case
