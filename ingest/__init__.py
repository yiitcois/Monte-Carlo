from .detect import detect_format
from . import msproject_xml, primavera_xer, csv_generic

READERS = {
    "msproject_xml": msproject_xml.read,
    "primavera_xer": primavera_xer.read,
    "csv_generic": csv_generic.read,
}
