# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

SECRET_KEY = 'this is not a secret key'

try:
    import sys
    UNIT_TESTING = 'test' == sys.argv[1]
except IndexError:
    UNIT_TESTING = False

INSTALLED_APPS = (
    'django.contrib.sites',
    'casexml.apps.case',
    'casexml.apps.phone',
    'casexml.apps.stock',
    'couchdbkit.ext.django',
    'couchforms',
    'django.contrib.contenttypes',
    'django.contrib.auth',
)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'casexml',
    }
}



####### Couch Config ######
COUCH_HTTPS = False # recommended production value is True if enabling https
COUCH_SERVER_ROOT = '127.0.0.1:5984' #6984 for https couch
COUCH_USERNAME = ''
COUCH_PASSWORD = ''
COUCH_DATABASE_NAME = 'casexml'

COUCH_DATABASE = 'http://127.0.0.1:5984/casexml_test'

COUCHDB_DATABASES = [ (app, 'http://127.0.0.1:5984/casexml') for app in ['case', 'couch', 'couchforms', 'phone'] ]


TEST_RUNNER = 'couchdbkit.ext.django.testrunner.CouchDbKitTestSuiteRunner'

####### # Email setup ########
# Print emails to console so there is no danger of spamming, but you can still get registration URLs
EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'
EMAIL_LOGIN = "nobody@example.com"
EMAIL_PASSWORD = "******"
EMAIL_SMTP_HOST = "smtp.example.com"
EMAIL_SMTP_PORT = 587

COVERAGE_REPORT_HTML_OUTPUT_DIR='coverage-html'
COVERAGE_MODULE_EXCLUDES= ['tests$', 'settings$', 'urls$', 'locale$',
                           'common.views.test', '^django', 'management', 'migrations',
                           '^south', '^djcelery', '^debug_toolbar', '^rosetta']
ROOT_URLCONF = "reference_urls"

# Disable logging from casexml
LOGGING = {
    'version': 1,
    'handlers': {
        'null': {
            'level': 'DEBUG',
            'class': 'django.utils.log.NullHandler',
        },
    },
    'loggers': {
        '': {
            'level': 'CRITICAL',
            'handler': 'null',
            'propagate': False,
        }
    }
}

SITE_ID = 1
