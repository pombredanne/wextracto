from wex.extractor import label, Named
from wex.response import Response
from wex.etree import xpath, text


attrs = Named(
    name = xpath('//h1') | text,
    country = xpath('//dd[@id="country"]') | text,
    region = xpath('//dd[@id="region"]') | text
)

extract = label(Response.geturl)(attrs)
