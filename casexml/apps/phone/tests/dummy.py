from datetime import datetime
from casexml.apps.phone.models import User

def dummy_user():
    return User(user_id="foo", username="mclovin", 
                password="changeme", date_joined=datetime(2011, 6, 9), 
                user_data={"something": "arbitrary"})

def dummy_user_xml():
        return """
    <Registration xmlns="http://openrosa.org/user/registration">
        <username>mclovin</username>
        <password>changeme</password>
        <uuid>foo</uuid>
        <date>2011-06-09</date>
        <user_data>
            <data key="something">arbitrary</data>
        </user_data>
    </Registration>"""
    
def dummy_restore_xml(restore_id, case_xml=""):
        return """
<OpenRosaResponse xmlns="http://openrosa.org/http/response">
    <message nature="ota_restore_success">Successfully restored account mclovin!</message>
    <Sync xmlns="http://commcarehq.org/sync">
        <restore_id>%(restore_id)s</restore_id> 
    </Sync>
    %(user_xml)s
    %(case_xml)s
</OpenRosaResponse>""" % {"restore_id": restore_id,
                          "user_xml": dummy_user_xml(),
                          "case_xml": case_xml}
    
    