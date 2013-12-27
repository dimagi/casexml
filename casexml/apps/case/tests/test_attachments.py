from django.test import TestCase
import os
from casexml.apps.case import settings
from casexml.apps.case.models import CommCareCase
from couchforms.util import post_xform_to_couch
from casexml.apps.case import process_cases
from django.core.files.uploadedfile import UploadedFile
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
import hashlib

class CaseAttachmentTest(TestCase):
    """
    Tests the use of attachments in cases
    """
    
    
    def setUp(self):
        settings.CASEXML_FORCE_DOMAIN_CHECK = False
        delete_all_cases()
        delete_all_xforms()


    def testAttachInCreate(self):
        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))
        
        file_path = os.path.join(os.path.dirname(__file__), "data", "attachments", "create_with_attach.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        
        attach_name = "fruity.jpg"
        attachment_path = os.path.join(os.path.dirname(__file__), "data", "attachments", attach_name)
        with open(attachment_path, "rb") as attachment:
            uf = UploadedFile(attachment, attach_name)
            form = post_xform_to_couch(xml_data, {attach_name: uf})
            self.assertEqual(1, len(form.attachments))
            fileback = form.fetch_attachment(attach_name)
            # rewind the pointer before comparing
            attachment.seek(0) 
            self.assertEqual(hashlib.md5(fileback).hexdigest(), 
                             hashlib.md5(attachment.read()).hexdigest())
            
        
        process_cases(form)
        case = CommCareCase.get(form.xpath("form/case/case_id"))
        self.assertEqual(1, len(case.attachments))
        self.assertEqual(form.get_id, case.attachments[0][0])
        self.assertEqual(attach_name, case.attachments[0][1])
        
    
    def testAttachInUpdate(self):
        self.testAttachInCreate()
        
        file_path = os.path.join(os.path.dirname(__file__), "data", "attachments", "update_with_attach.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        
        attach_name = "house.jpg"
        attachment_path = os.path.join(os.path.dirname(__file__), "data", "attachments", attach_name)
        with open(attachment_path, "rb") as attachment:
            uf = UploadedFile(attachment, attach_name)
            form = post_xform_to_couch(xml_data, {attach_name: uf})
            self.assertEqual(1, len(form.attachments))
            fileback = form.fetch_attachment(attach_name)
            # rewind the pointer before comparing
            attachment.seek(0) 
            self.assertEqual(hashlib.md5(fileback).hexdigest(), 
                             hashlib.md5(attachment.read()).hexdigest())
            
        
        process_cases(form)
        case = CommCareCase.get(form.xpath("form/case/case_id"))
        self.assertEqual(2, len(case.attachments))
        self.assertEqual(form.get_id, case.attachments[1][0])
        self.assertEqual(attach_name, case.attachments[1][1])
                
        
