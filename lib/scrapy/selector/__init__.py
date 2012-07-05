"""
XPath selectors

Two backends are currently available: libxml2 and lxml

To select the backend explicitly use the SELECTORS_BACKEND variable in your
project. Otherwise, libxml2 will be tried first. If libxml2 is not available,
lxml will be used.
"""

import lxml
from scrapy.selector.lxmlsel import *

# try:
#     import libxml2
# except ImportError:
#     try:
#         import lxml
#     except ImportError:
#         from scrapy.selector.dummysel import *
#     else:
#         from scrapy.selector.lxmlsel import *
# else:
#     from scrapy.selector.libxml2sel import *
