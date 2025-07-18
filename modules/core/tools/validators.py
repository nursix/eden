"""
    Validators

    Copyright: (c) 2010-2022 Sahana Software Foundation

    Permission is hereby granted, free of charge, to any person
    obtaining a copy of this software and associated documentation
    files (the "Software"), to deal in the Software without
    restriction, including without limitation the rights to use,
    copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following
    conditions:

    The above copyright notice and this permission notice shall be
    included in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
    EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
    OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
    NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
    HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
    WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
    OTHER DEALINGS IN THE SOFTWARE.
"""

__all__ = ("IS_DYNAMIC_FIELDNAME",
           "IS_DYNAMIC_FIELDTYPE",
           "IS_FLOAT_AMOUNT",
           "IS_HTML_COLOUR",
           "IS_IBAN",
           "IS_INT_AMOUNT",
           "IS_IN_SET_LAZY",
           "IS_ISO639_2_LANGUAGE_CODE",
           "IS_JSONS3",
           "IS_LAT",
           "IS_LON",
           "IS_LAT_LON",
           "IS_LOCATION",
           "IS_NUMBER",
           "IS_ONE_OF",
           "IS_ONE_OF_EMPTY",
           "IS_ONE_OF_EMPTY_SELECT",
           "IS_NOT_ONE_OF",
           "IS_PERSON_GENDER",
           "IS_PHONE_NUMBER_SINGLE",
           "IS_PHONE_NUMBER_MULTI",
           "IS_PROCESSED_IMAGE",
           "IS_UTC_DATETIME",
           "IS_UTC_DATE",
           "IS_UTC_OFFSET",
           "IS_AVAILABLE_QUANTITY",
           "SKIP_VALIDATION",
           "SINGLE_PHONE_NUMBER_PATTERN",
           "MULTI_PHONE_NUMBER_PATTERN",
           "JSONERRORS",
           )

import datetime
import json
import re

from functools import reduce
from io import BytesIO
from uuid import uuid4

from gluon import current, DIV, IS_FLOAT_IN_RANGE, IS_INT_IN_RANGE, IS_IN_SET, \
                  IS_MATCH, IS_NOT_IN_DB
from gluon.storage import Storage
from gluon.validators import Validator, ValidationError

from .calendar import S3DateTime
from .convert import s3_str
from .utils import s3_orderby_fields, JSONSEPARATORS

DEFAULT = lambda: None
JSONERRORS = (NameError, TypeError, ValueError, AttributeError, KeyError)

LAT_SCHEMA = re.compile(r"^([0-9]{,3})[d:°]{,1}\s*([0-9]{,3})[m:']{,1}\s*([0-9]{,3}(\.[0-9]+){,1})[s\"]{,1}\s*([N|S]{,1})$")
LON_SCHEMA = re.compile(r"^([0-9]{,3})[d:°]{,1}\s*([0-9]{,3})[m:']{,1}\s*([0-9]{,3}(\.[0-9]+){,1})[s\"]{,1}\s*([E|W]{,1})$")
IBAN_SCHEMA = re.compile(r"([A-Z]{2})([0-9]{2})([0-9A-Z]{4,30})")

def translate(text):
    if text is None:
        return None
    elif isinstance(text, str):
        if hasattr(current, "T"):
            return str(current.T(text))
    return s3_str(text)

def options_sorter(x, y):
    return 1 if s3_str(x[1]).upper() > s3_str(y[1]).upper() else -1

def validator_caller(func, value, record_id=None):
    validate = getattr(func, "validate", None)
    if validate and validate is not Validator.validate:
        return validate(value, record_id)
    value, error = func(value)
    if error is not None:
        raise ValidationError(error)
    return value

# =============================================================================
class IS_JSONS3(Validator):
    """
        Similar to web2py's IS_JSON validator, but extended to handle
        single quotes in dict keys (=invalid JSON) from CSV imports.

        Example:

            INPUT(_type='text', _name='name', requires=IS_JSONS3())

            >>> IS_JSONS3()('{"a": 100}')
            ({u'a': 100}, None)

            >>> IS_JSONS3()('spam1234')
            ('spam1234', 'invalid json')
    """

    def __init__(self,
                 native_json = False,
                 error_message = "Invalid JSON",
                 fix_quotes = False,
                 ):
        """
            Args:
                native_json: return the JSON string rather than
                             a Python object (e.g. when the field
                             is "string" type rather than "json")
                error_message: alternative error message
                fix_quotes: fix invalid JSON with single quotes
        """

        self.native_json = native_json
        self.error_message = error_message
        self.fix_quotes = fix_quotes

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validator

            Args:
                value: the input value
                record_id: the current record ID (unused, for API compatibility)

            Returns:
                the parsed JSON (or the original JSON string)
        """

        error = lambda e: "%s: %s" % (current.T(self.error_message), e)

        if self.fix_quotes or current.response.s3.bulk:
            # CSV import produces invalid JSON (single quotes),
            # which would still be valid Python though, so try
            # using ast to decode, then re-dumps as valid JSON:
            import ast
            invalid = JSONERRORS + (SyntaxError,)
            try:
                v = json.dumps(ast.literal_eval(value),
                               separators = JSONSEPARATORS,
                               )
            except invalid as e:
                raise ValidationError(error(e)) from e
            ret = v if self.native_json else json.loads(v)
        else:
            # Coming from UI, so expect valid JSON
            try:
                parsed = json.loads(value)
            except JSONERRORS as e:
                raise ValidationError(error(e)) from e
            ret = value if self.native_json else parsed

        return ret

    # -------------------------------------------------------------------------
    def formatter(self, value):
        """
            Formatter, converts the db format into a string

            Args:
                value: the database value

            Returns:
                JSON string
        """

        if value is None or \
           self.native_json and isinstance(value, str):
            return value
        else:
            return json.dumps(value, separators = JSONSEPARATORS)

# =============================================================================
class IS_LAT(Validator):
    """
        Latitude has to be in decimal degrees between -90 & 90
        - we attempt to convert DMS format into decimal degrees

        Example:
            INPUT(_type="text", _name="name", requires=IS_LAT())
    """

    def __init__(self,
                 error_message = "Latitude/Northing should be between -90 & 90!"
                 ):
        """
            Args:
                error_message: alternative error message
        """

        self.error_message = error_message

        # Tell s3_mark_required that this validator doesn't accept NULL values
        self.mark_required = True

        self.schema = LAT_SCHEMA
        self.minimum = -90
        self.maximum = 90

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validator

            Args:
                value: the input value
                record_id: the current record ID (unused, for API compatibility)

            Returns:
                the value (converted to decimal degrees)
        """

        if value is None:
            raise ValidationError(self.error_message)
        try:
            value = float(value)
        except ValueError as e:
            # DMS format
            match = self.schema.match(value)
            if not match:
                raise ValidationError(self.error_message) from e
            try:
                d = float(match.group(1))
                m = float(match.group(2))
                s = float(match.group(3))
            except (ValueError, TypeError) as ee:
                raise ValidationError(self.error_message) from ee

            h = match.group(5)
            sign = -1 if h in ("S", "W") else 1

            deg = sign * (d + m / 60 + s / 3600)
        else:
            deg = value

        if self.minimum <= deg <= self.maximum:
            return deg

        raise ValidationError(self.error_message)

# =============================================================================
class IS_LON(IS_LAT):
    """
        example:

        INPUT(_type="text", _name="name", requires=IS_LON())

        Longitude has to be in decimal degrees between -180 & 180
        - we attempt to convert DMS format into decimal degrees
    """

    def __init__(self,
                 error_message = "Longitude/Easting should be between -180 & 180!"
                 ):
        """
            Args:
                error_message: alternative error message
        """

        super().__init__(error_message=error_message)

        self.schema = LON_SCHEMA
        self.minimum = -180
        self.maximum = 180

# =============================================================================
class IS_LAT_LON(Validator):
    """
        Designed for use within the S3LocationLatLonWidget
    """

    def __init__(self, field):
        """
            Args:
                field: the location Field (used to determine the
                       names of the lat/lon inputs)
        """

        self.field = field

        # Tell s3_mark_required that this validator doesn't accept NULL values
        self.mark_required = True

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validate lat/lon input related to a location

            Args:
                value: the gis_location ID
                record_id: the current record ID (unused, for API compatibility)

            Returns:
                the gis_location ID
        """

        if current.response.s3.bulk:
            # Pointless in imports
            return value

        selector = str(self.field).replace(".", "_")

        # Read lat/lon input from post_vars
        post_vars = current.request.post_vars
        lat = post_vars.get("%s_lat" % selector, None)
        if lat == "":
            lat = None
        lon = post_vars.get("%s_lon" % selector, None)
        if lon == "":
            lon = None

        if lat is None or lon is None:
            # We don't accept None
            raise ValidationError(current.T("Latitude and Longitude are required"))

        # Validate lat and lon (also converts them to decimal degrees)
        lat = IS_LAT().validate(lat)
        lon = IS_LON().validate(lon)

        # TODO Audit
        if value:
            # Existing location
            db = current.db
            db(db.gis_location.id == value).update(lat=lat, lon=lon)
        else:
            # New location
            value = current.db.gis_location.insert(lat=lat, lon=lon)

        return value

# =============================================================================
class IS_NUMBER:
    """
        Used by s3data.py to wrap IS_INT_AMOUNT & IS_FLOAT_AMOUNT
    """

    # -------------------------------------------------------------------------
    @staticmethod
    def represent(number, precision=2):
        """
            Represent a number with thousands-separator

            Args:
                number: the number
                precision: number of decimal places

            Returns:
                string representation of the number
        """

        if number is None:
            return ""
        if isinstance(number, int):
            return IS_INT_AMOUNT.represent(number)
        elif isinstance(number, float):
            return IS_FLOAT_AMOUNT.represent(number, precision)
        else:
            return s3_str(number)

# =============================================================================
class IS_INT_AMOUNT(IS_INT_IN_RANGE):
    """
        Validation, widget and representation of integer-values
        with thousands-separator
    """

    def __init__(self,
                 minimum = None,
                 maximum = None,
                 error_message = None,
                 ):
        """
            Args:
                minimum: the minimum allowed value
                maximum: the maximum allowed value
                error_message: alternative error message
        """

        IS_INT_IN_RANGE.__init__(self,
                                 minimum=minimum,
                                 maximum=maximum,
                                 error_message=error_message,
                                 )

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validator

            Args:
                value: the input value
                record_id: the current record ID (unused, for API compatibility)

            Returns:
                the value (integer)
        """

        thousands_sep = current.deployment_settings.get_L10n_thousands_separator()
        if thousands_sep:
            value = s3_str(value).replace(thousands_sep, "")

        return IS_INT_IN_RANGE.validate(self, value, record_id=record_id)

    # -------------------------------------------------------------------------
    @staticmethod
    def represent(number):
        """
            Change the format of the number depending on the language
            Based on https://code.djangoproject.com/browser/django/trunk/django/utils/numberformat.py

            Args:
                number: the number

            Returns:
                string representation of the number
        """

        if number is None:
            return ""
        try:
            intnumber = int(number)
        except ValueError:
            intnumber = number

        settings = current.deployment_settings
        THOUSAND_SEPARATOR = settings.get_L10n_thousands_separator()
        NUMBER_GROUPING = settings.get_L10n_thousands_grouping()

        # The negative/positive sign for the number
        if float(number) < 0:
            sign = "-"
        else:
            sign = ""

        str_number = str(intnumber)

        if str_number[0] == "-":
            str_number = str_number[1:]

        # Walk backwards over the integer part, inserting the separator as we go
        int_part_gd = ""
        for cnt, digit in enumerate(str_number[::-1]):
            if cnt and not cnt % NUMBER_GROUPING:
                int_part_gd += THOUSAND_SEPARATOR
            int_part_gd += digit
        int_part = int_part_gd[::-1]

        return sign + int_part

    # -------------------------------------------------------------------------
    @staticmethod
    def widget(field, value, **attributes):
        """
            A form widget for int amounts, replacing the default
            "integer" CSS class with "int_amount"

            Args:
                field: the Field
                value: the current field value
                attributes: DOM attributes for the widget

            Returns:
                the form widget (INPUT)
        """

        from gluon.sqlhtml import StringWidget

        attr = dict(attributes)

        css_class = attr.get("_class")

        classes = set(css_class.split(" ")) if css_class else set()
        classes.discard("integer")
        classes.add("int_amount")

        attr["_class"] = " ".join(classes)

        return StringWidget.widget(field, value, **attr)

# =============================================================================
class IS_FLOAT_AMOUNT(IS_FLOAT_IN_RANGE):
    """
        Validation, widget and representation of
        float-values with thousands-separators
    """

    def __init__(self,
                 minimum = None,
                 maximum = None,
                 error_message = None,
                 dot = None,
                 ):
        """
            Args:
                minimum: the minimum allowed value
                maximum: the maximum allowed value
                error_message: alternative error message
                dot: alternative decimal separator
        """

        if dot is None:
            dot = current.deployment_settings.get_L10n_decimal_separator()

        IS_FLOAT_IN_RANGE.__init__(self,
                                   minimum=minimum,
                                   maximum=maximum,
                                   error_message=error_message,
                                   dot=dot,
                                   )

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validator

            Args:
                value: the input value
                record_id: the current record_id (unused, for API-compatibility)

            Returns:
                the value (as float)
        """

        # Strip the thousands-separator
        thousands_sep = current.deployment_settings.get_L10n_thousands_separator()
        if thousands_sep and isinstance(value, str):
            value = s3_str(s3_str(value).replace(thousands_sep, ""))

        return IS_FLOAT_IN_RANGE.validate(self, value, record_id=record_id)

    # -------------------------------------------------------------------------
    @staticmethod
    def represent(number, precision=None, fixed=False):
        """
            Change the format of the number depending on the language
            Based on https://code.djangoproject.com/browser/django/trunk/django/utils/numberformat.py

            Args:
                number: the number
                precision: the number of decimal places to show
                fixed: show (trailing) decimal places even if they are 0

            Returns:
                string representation of the number
        """

        if number is None:
            return ""

        DECIMAL_SEPARATOR = current.deployment_settings.get_L10n_decimal_separator()

        if precision is not None:
            str_number = format(number, ".0%df" % precision)
        else:
            # Default to any precision
            str_number = format(number, "f").rstrip("0") \
                                            .rstrip(DECIMAL_SEPARATOR)

        if "." in str_number:
            int_part, dec_part = str_number.split(".")
        else:
            int_part, dec_part = str_number, ""

        if dec_part and not fixed:
            # Omit decimal part if zero
            if int(dec_part) == 0:
                dec_part = ""
            # Remove trailing zeros
            dec_part = dec_part.rstrip("0")

        if dec_part:
            dec_part = DECIMAL_SEPARATOR + dec_part

        int_part = IS_INT_AMOUNT.represent(int(int_part))

        return int_part + dec_part

    # -------------------------------------------------------------------------
    @staticmethod
    def widget(field, value, **attributes):
        """
            A form widget for float amounts, replacing the default
            "double" CSS class with "float_amount"

            Args:
                field: the Field
                value: the current field value
                attributes: DOM attributes for the widget

            Returns:
                the form widget (INPUT)
        """

        from gluon.sqlhtml import StringWidget

        attr = dict(attributes)

        css_class = attr.get("_class")

        classes = set(css_class.split(" ")) if css_class else set()
        classes.discard("double")
        classes.add("float_amount")

        attr["_class"] = " ".join(classes)

        return StringWidget.widget(field, value, **attr)

# =============================================================================
class IS_HTML_COLOUR(IS_MATCH):
    """
        Example::

        INPUT(_type="text", _name="name", requires=IS_HTML_COLOUR())
    """

    def __init__(self,
                 error_message="must be a 6 digit hex code! (format: rrggbb)"
                ):
        """
            Args:
                error_message: alternative error message
        """

        IS_MATCH.__init__(self, "^[0-9a-fA-F]{6}$",
                          error_message = error_message,
                          )

    # -------------------------------------------------------------------------
    @staticmethod
    def represent(value, row=None):
        """
            Represent a HTML color

            Args:
                value: the color value as 6-digit hex code, or None
                row: unused, for compatibility
            Returns:
                DIV
        """

        if value:
            value = DIV(str(value),
                        _class = "color-represent",
                        # TODO move padding into theme
                        _style = "background-color:#%s;padding:0 5px;" % value,
                        )
        return value

# =============================================================================
REGEX1 = re.compile(r"[\w_]+\.[\w_]+")
REGEX2 = re.compile(r"%\((?P<name>[^\)]+)\)s")

class IS_ONE_OF_EMPTY(Validator):
    """
        Filtered version of IS_IN_DB():

        validates a given value as key of another table, filtered by the
        'filterby' field for one of the 'filter_opts' options
        (=a selective IS_IN_DB())

        NB Filtering isn't active in GQL.

        For the dropdown representation:

            'label' can be a string template for the record, or a set of field
            names of the fields to be used as option labels, or a function or
            lambda to create an option label from the respective record (which
            has to return a string, of course). The function will take the
            record as an argument.

            No 'options' method as designed to be called next to an
            Autocomplete field so don't download a large dropdown
            unnecessarily.
    """

    def __init__(self,
                 dbset,
                 field,
                 label = None, *,
                 filterby = None,
                 filter_opts = None,
                 not_filterby = None,
                 not_filter_opts = None,
                 realms = None,
                 updateable = False,
                 instance_types = None,
                 error_message = "invalid value!",
                 orderby = None,
                 groupby = None,
                 left = None,
                 multiple = False,
                 zero = "",
                 sort = True,
                 _and = None,
                 ):
        """
            Args:
                dbset: a Set of records like db(query), or db itself
                field: the field in the referenced table
                label: lookup method for the label corresponding a value,
                       alternatively a string template to be filled with
                       values from the record
                filterby: a field in the referenced table to filter by
                filter_opts: values for the filterby field which indicate
                             records to include
                not_filterby: a field in the referenced table to filter by
                not_filter_opts: values for not_filterby field which indicate
                                 records to exclude
                realms: only include records belonging to the listed realms
                        (if None, all readable records will be included)
                updateable: only include records in the referenced table which
                            can be updated by the user (if False, all readable
                            records will be included)
                instance_types: if the referenced table is a super-entity, then
                                only include these instance types (this parameter
                                is required for super entity lookups!)
                error_message: the error message to return for failed validation
                orderby: orderby for the options
                groupby: groupby for the options
                left: additional left joins required for the options lookup
                      (super-entity instance left joins will be included
                      automatically)
                multiple: allow multiple values (for list:reference types)
                zero: add this as label for the None-option (allow selection of "None")
                sort: sort options alphabetically by their label
                _and: internal use
        """

        if hasattr(dbset, "define_table"):
            self.dbset = dbset()
        else:
            self.dbset = dbset
        (ktable, kfield) = str(field).split(".")
        if not kfield:
            kfield = "id"

        self.ktable = ktable
        self.kfield = kfield

        self.label = label
        self._fields = None

        self.error_message = error_message

        self.theset = None
        self.labels = None

        self._orderby = orderby
        self.groupby = groupby
        self.left = left
        self.multiple = multiple
        self.zero = zero
        self.sort = sort
        self._and = _and

        self.filterby = filterby
        self.filter_opts = filter_opts
        self.not_filterby = not_filterby
        self.not_filter_opts = not_filter_opts

        self.realms = realms
        self.updateable = updateable
        self.instance_types = instance_types

    # -------------------------------------------------------------------------
    @property
    def orderby(self):
        """
            Orderby rule for building the set (lazy property)

            Returns:
                the orderby expression
        """

        return self._orderby if self.fields else None

    # -------------------------------------------------------------------------
    @property
    def fields(self):
        """
            Fields to load before representation (lazy property)

            Returns:
                list of field names (incl. tablename prefixes)
        """

        fields = self._fields
        if fields is None:

            label = self.label
            ktable, kfield = self.ktable, self.kfield

            pkey = "%s.%s" % (ktable, kfield)

            if not label:
                label = "%%(%s)s" % kfield
                fields = [pkey]
                # Include name-field as fallback for build-set
                table = current.s3db.table(ktable)
                if table and "name" in table.fields:
                    fields.append("name")
            elif hasattr(label, "bulk"):
                # S3Represent
                if label.custom_lookup:
                    # Represent uses a custom lookup, so we only
                    # retrieve the keys here
                    fields = [pkey]
                    if self._orderby is None:
                        self._orderby = fields[0]
                else:
                    # Represent uses a standard field lookup, so
                    # we can do that right here
                    label._setup()
                    fields = list(label.fields)
                    if pkey not in fields:
                        fields.insert(0, pkey)
            elif callable(label):
                # Represent function
                fields = [pkey]
            elif isinstance(label, str):
                if REGEX1.match(label):
                    label = "%%(%s)s" % label.split(".")[-1]
                ks = REGEX2.findall(label)
                if not kfield in ks:
                    ks += [kfield]
                fields = ["%s.%s" % (ktable, k) for k in ks]
            elif isinstance(label, (tuple, list)):
                fields = ["%s.%s" % (ktable, k) for k in label]
                if pkey not in fields:
                    fields.insert(0, pkey)
            else:
                fields = "all"

            self._fields = fields

        return fields

    # -------------------------------------------------------------------------
    def set_self_id(self, record_id):
        """
            Set the current record ID

            Args:
                record_id: the current record ID

            Notes:
                - deprecated in PyDAL, but still used in web2py and Eden
                - record_id not used here, but propagated to _and
        """

        if self._and:
            self._and.record_id = record_id

    # -------------------------------------------------------------------------
    def set_filter(self,
                   filterby = None,
                   filter_opts = None,
                   not_filterby = None,
                   not_filter_opts = None,
                   ):
        """
            This can be called from prep to apply a filter based on
            data in the record or the primary resource id.

            Args:
                filterby: the field to filter by
                filter_opts: the values to match
                not_filterby: the field to filter by
                not_filter_opts: the values to exclude
        """

        if filterby:
            self.filterby = filterby
            self.filter_opts = filter_opts

        if not_filterby:
            self.not_filterby = not_filterby
            self.not_filter_opts = not_filter_opts

    # -------------------------------------------------------------------------
    def build_set(self):
        """
            Look up selectable options from the database
        """

        dbset = self.dbset
        db = dbset._db

        ktablename = self.ktable
        if ktablename not in db:
            table = current.s3db.table(ktablename, db_only=True)
        else:
            table = db[ktablename]

        if not table:
            self.theset = None
            self.labels = None
            return

        if self.fields == "all":
            fields = [table[f] for f in table.fields if f not in ("wkt", "the_geom")]
        else:
            fieldnames = [f.split(".")[1] if "." in f else f for f in self.fields]
            fields = [table[k] for k in fieldnames if k in table.fields]

        if db._dbname not in ("gql", "gae"):

            orderby = self.orderby or reduce(lambda a, b: a|b, fields)
            groupby = self.groupby

            left = self.left

            dd = {"orderby": orderby, "groupby": groupby}
            query, qleft = self.query(table, fields=fields, dd=dd)
            if qleft is not None:
                if left is not None:
                    if not isinstance(qleft, list):
                        qleft = [qleft]
                    ljoins = [str(join) for join in left]
                    for join in qleft:
                        ljoin = str(join)
                        if ljoin not in ljoins:
                            left.append(join)
                            ljoins.append(ljoin)
                else:
                    left = qleft
            if left is not None:
                dd["left"] = left

            # Make sure we have all ORDERBY fields in the query
            # - required with distinct=True (PostgreSQL)
            fieldnames = set(str(f) for f in fields)
            for f in s3_orderby_fields(table, dd.get("orderby")):
                fieldname = str(f)
                if fieldname not in fieldnames:
                    fields.append(f)
                    fieldnames.add(fieldname)

            records = dbset(query).select(distinct=True, *fields, **dd)

        else:
            # Note this does not support filtering.
            orderby = self.orderby or \
                      reduce(lambda a, b: a|b, (f for f in fields if f.type != "id"))
            records = dbset.select(table.ALL,
                                   # Caching breaks Colorbox dropdown refreshes
                                   #cache=(current.cache.ram, 60),
                                   orderby = orderby,
                                   )

        self.theset = [str(r[self.kfield]) for r in records]

        label = self.label
        try:
            # Is callable
            if hasattr(label, "bulk"):
                # S3Represent => use bulk option
                d = label.bulk(None,
                               rows = records,
                               list_type = False,
                               show_link = False,
                               )
                labels = [d.get(r[self.kfield], d[None]) for r in records]
            else:
                # Other representation function
                labels = [label(r) for r in records]
        except TypeError:
            if isinstance(label, str):
                labels = [label % dict(r) for r in records]
            elif isinstance(label, (list, tuple)):
                labels = [" ".join([r[l] for l in label if l in r])
                          for r in records
                          ]
            elif "name" in table:
                labels = [r.name for r in records]
            else:
                labels = [r[self.kfield] for r in records]
        self.labels = labels

        if labels and self.sort:
            items = sorted(zip(self.theset, self.labels),
                           key = lambda item: s3_str(item[1]).lower(),
                           )
            self.theset, self.labels = zip(*items)

    # -------------------------------------------------------------------------
    def query(self, table, fields=None, dd=None):
        """
            Construct the query to lookup the options (separated from
            build_set so the query can be extracted and used in other
            lookups, e.g. filter options).

            Args:
                table: the lookup table
                fields: fields (updatable list)
                dd: additional query options (updatable dict)

            Returns:
                tuple (query, left)
        """

        # Accessible-query
        method = "update" if self.updateable else "read"
        query, left = self.accessible_query(method, table,
                                            instance_types=self.instance_types)

        # Available-query
        if "deleted" in table:
            query &= (table["deleted"] == False)

        # Realms filter?
        if self.realms:
            auth = current.auth
            if auth.is_logged_in() and \
               auth.get_system_roles().ADMIN in auth.user.realms:
                # Admin doesn't filter
                pass
            else:
                query &= auth.permission.realm_query(table, self.realms)

        all_fields = [str(f) for f in fields] if fields is not None else []

        filterby = self.filterby
        if filterby and filterby in table:

            filter_opts = self.filter_opts

            if filter_opts is not None:
                if None in filter_opts:
                    # Needs special handling (doesn't show up in 'belongs')
                    _query = (table[filterby] == None)
                    filter_opts = [f for f in filter_opts if f is not None]
                    if filter_opts:
                        _query = _query | (table[filterby].belongs(filter_opts))
                    query &= _query
                else:
                    query &= (table[filterby].belongs(filter_opts))

            if not self.orderby and \
               fields is not None and dd is not None:
                filterby_field = table[filterby]
                if dd is not None:
                    dd.update(orderby=filterby_field)
                if str(filterby_field) not in all_fields:
                    fields.append(filterby_field)
                    all_fields.append(str(filterby_field))

        not_filterby = self.not_filterby
        if not_filterby and not_filterby in table:

            not_filter_opts = self.not_filter_opts

            if not_filter_opts:
                if None in not_filter_opts:
                    # Needs special handling (doesn't show up in 'belongs')
                    _query = (table[not_filterby] == None)
                    not_filter_opts = [f for f in not_filter_opts if f is not None]
                    if not_filter_opts:
                        _query = _query | (table[not_filterby].belongs(not_filter_opts))
                    query &= (~_query)
                else:
                    query &= (~(table[not_filterby].belongs(not_filter_opts)))

            if not self.orderby and \
               fields is not None and dd is not None:
                filterby_field = table[not_filterby]
                if dd is not None:
                    dd.update(orderby=filterby_field)
                if str(filterby_field) not in all_fields:
                    fields.append(filterby_field)
                    all_fields.append(str(filterby_field))

        return query, left

    # -------------------------------------------------------------------------
    @classmethod
    def accessible_query(cls, method, table, instance_types=None):
        """
            Returns an accessible query (and left joins, if necessary) for
            records in table the user is permitted to access with method

            Args:
                method: the method (e.g. "read" or "update")
                table: the table
                instance_types: list of instance tablenames, if table is
                                a super-entity (required in this case!)

            Returns:
                tuple (query, left) where query is the query and left joins
                is the list of left joins required for the query

            Note:
                For higher security policies and super-entities with many
                instance types this can give a very complex query. Try to
                always limit the instance types to what is really needed
        """

        DEFAULT = (table._id > 0)

        left = None

        if "instance_type" in table:
            # Super-entity
            if not instance_types:
                return DEFAULT, left
            query = None
            auth = current.auth
            s3db = current.s3db
            for instance_type in instance_types:
                itable = s3db.table(instance_type)
                if itable is None:
                    continue

                join = itable.on(itable[table._id.name] == table._id)
                if left is None:
                    left = [join]
                else:
                    left.append(join)

                q = (itable._id != None) & \
                    auth.s3_accessible_query(method, itable)
                if "deleted" in itable:
                    q &= itable.deleted == False
                if query is None:
                    query = q
                else:
                    query |= q

            if query is None:
                query = DEFAULT
        else:
            query = current.auth.s3_accessible_query(method, table)

        return query, left

    # -------------------------------------------------------------------------
    # Removed as we don't want any options downloaded unnecessarily
    #def options(self):

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validator

            Args:
                value: the input value
                record_id: the current record ID

            Returns:
                the value
        """

        dbset = self.dbset
        table = dbset._db[self.ktable]

        # Deleted-query
        deleted_q = (table["deleted"] == False) if ("deleted" in table) else False

        # Build filter query
        filter_opts_q = False
        filterby = self.filterby
        if filterby and filterby in table:
            filter_opts = self.filter_opts
            if filter_opts:
                if None in filter_opts:
                    # Needs special handling (doesn't show up in 'belongs')
                    filter_opts_q = (table[filterby] == None)
                    filter_opts = [f for f in filter_opts if f is not None]
                    if filter_opts:
                        filter_opts_q |= (table[filterby].belongs(filter_opts))
                else:
                    filter_opts_q = (table[filterby].belongs(filter_opts))

        if self.multiple:
            # Multiple values
            if isinstance(value, list):
                values = [str(v) for v in value]
            elif isinstance(value, str):
                if not value:
                    values = []
                elif len(value) > 2 and value[0] == "|" and value[-1] == "|":
                    values = value[1:-1].split("|")
                else:
                    values = [value]
            elif value:
                values = [value]
            else:
                values = []

            if self.theset:
                # Pre-built set
                if not [x for x in values if not x in self.theset]:
                    return values
            else:
                # No pre-built set
                field = table[self.kfield]
                query = None
                for v in values:
                    q = (field == v)
                    query = (query | q) if query is not None else q
                if filter_opts_q != False:
                    query = (filter_opts_q & (query)) \
                            if query is not None else filter_opts_q
                if deleted_q != False:
                    query = (deleted_q & (query)) \
                            if query is not None else deleted_q
                if dbset(query).count() == len(values):
                    return values

        elif self.theset:
            # Single value, pre-built set
            if str(value) in self.theset:
                if self._and:
                    return validator_caller(self._and, value, record_id)
                else:
                    return value

        else:
            # Single value, no pre-built set
            query = (table[self.kfield] == value)
            if filter_opts_q is not False:
                query &= filter_opts_q
            if deleted_q is not False:
                query &= deleted_q
            if dbset(query).count():
                if self._and:
                    return validator_caller(self._and, value, record_id)
                else:
                    return value

        raise ValidationError(translate(self.error_message))

# =============================================================================
class IS_ONE_OF_EMPTY_SELECT(IS_ONE_OF_EMPTY):
    """
        Extends IS_ONE_OF_EMPTY by displaying an empty SELECT
        (instead of INPUT).

        Note:
            Fields with this validator should also use the EmptyOptionsWidget
            to ensure the previously selected option is passed to filterOptionsS3
            in order to be re-selected after the initial options lookup
    """

    @staticmethod
    def options(zero=True):
        return [("", "")]

# =============================================================================
class IS_ONE_OF(IS_ONE_OF_EMPTY):
    """
        Extends IS_ONE_OF_EMPTY by restoring the 'options' method.
    """

    def options(self, zero=True):
        """
            Get the valid options for this validator

            Args:
                zero: include an empty-option (overrides self.zero)
        """

        self.build_set()
        theset, labels = self.theset, self.labels
        if theset is None or labels is None:
            items = []
        else:
            items = list(zip(theset, labels))
        if zero and self.zero is not None and not self.multiple:
            items.insert(0, ("", self.zero))
        return items

# =============================================================================
class IS_NOT_ONE_OF(IS_NOT_IN_DB):
    """
        Filtered version of IS_NOT_IN_DB()
            - understands the 'deleted' field.
            - makes the field unique (amongst non-deleted field)

        Example:
            - INPUT(_type="text", _name="name", requires=IS_NOT_ONE_OF(db, db.table))
    """

    def __init__(self,
                 dbset,
                 field, *,
                 error_message = "Value already in database or empty",
                 allowed_override = None,
                 ignore_common_filters = False,
                 skip_imports = False,
                 ):
        """
            Args:
                dbset: the DB set
                field: the Field
                error_message: the error message
                allowed_override: permit duplicates of these values
                ignore_common_filters: enforce uniqueness beyond global
                                        table filters
                skip_import: do not validate during imports
                             (e.g. to let deduplicate take care of duplicates)
        """

        super().__init__(dbset,
                         field,
                         error_message = error_message,
                         allowed_override = allowed_override,
                         ignore_common_filters = ignore_common_filters,
                         )

        self.skip_imports = skip_imports

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validator

            Args:
                value: the input value
                record_id: the current record ID

            Returns:
                the value
        """

        value = str(value)
        if not value.strip():
            # Empty => error
            raise ValidationError(translate(self.error_message))

        allowed_override = self.allowed_override
        if allowed_override and value in allowed_override:
            # Uniqueness-requirement overridden
            return value

        # Establish table and field
        tablename, fieldname = str(self.field).split(".")
        dbset = self.dbset
        db = dbset if hasattr(dbset, "define_table") else dbset.db
        table = db[tablename]
        field = table[fieldname]

        if self.skip_imports and current.response.s3.bulk and not field.unique:
            # Uniqueness-requirement to be enforced by deduplicate
            # (which can't take effect if we reject the value here)
            return value

        # Does the table allow archiving ("soft-delete")?
        archived = "deleted" in table

        # Does the table use multiple columns as key?
        if record_id is None:
            record_id = self.record_id
        keys = list(record_id.keys()) if isinstance(record_id, dict) else None

        # Build duplicate query
        # => if the field has a unique-constraint, we must include
        #    archived ("soft-deleted") records, otherwise the
        #    validator will pass, but the DB-write will crash
        query = (field == value)
        if not field.unique and archived:
            query = (table["deleted"] == False) & query

        # Limit the fields we extract to just keys+deleted
        fields = []
        if keys:
            fields = [table[k] for k in keys]
        else:
            fields = [table._id]
        if archived:
            fields.append(table.deleted)

        # Find conflict
        row = dbset(query).select(limitby=(0, 1), *fields).first()
        if row:
            if keys:
                # Keyed table
                for f in keys:
                    if str(getattr(row, f)) != str(record_id[f]):
                        raise ValidationError(translate(self.error_message))

            elif str(row[table._id.name]) != str(record_id):

                if archived and row.deleted and field.type in ("string", "text"):
                    # Table supports archiving, and the conflicting
                    # record is "deleted" => try updating the archived
                    # record by appending a random tag to the field value
                    import random
                    tagged = "%s.[%s]" % (value,
                                          "".join(random.choice("abcdefghijklmnopqrstuvwxyz")
                                                  for _ in range(8))
                                          )
                    try:
                        row.update_record(**{fieldname: tagged})
                    except Exception as e:
                        # Failed => nothing else we can try
                        raise ValidationError(translate(self.error_message)) from e
                else:
                    raise ValidationError(translate(self.error_message))

        return value

# =============================================================================
class IS_LOCATION(Validator):
    """
        Allow all locations, or locations by level.
    """

    def __init__(self,
                 level = None,
                 error_message = None,
                 ):
        """
            Args:
                level: level (or list of levels) to restrict to
                error_message: alternative error message
        """

        self.level = level # can be a List or a single element

        if error_message:
            self.error_message = error_message
        else:
            self.error_message = current.T("Invalid Location!")

        # Make it like IS_ONE_OF to support PopupLink
        self.ktable = "gis_location"
        self.kfield = "id"

        # Tell s3_mark_required that this validator doesn't accept NULL values
        self.mark_required = True

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validator

            Args:
                value: the input value (location ID)
                record_id: the current record ID (unused, for API compatibility)

            Returns:
                location ID
        """

        level = self.level
        if level == "L0":
            # Use cached countries. This returns name if id is for a country.
            try:
                location_id = int(value)
            except ValueError:
                ok = False
            else:
                ok = current.gis.get_country(location_id)
        else:
            db = current.db
            table = db.gis_location
            query = (table.id == value) & (table.deleted == False)
            if level:
                if isinstance(level, (tuple, list)):
                    if None in level:
                        # None needs special handling
                        level = [l for l in level if l is not None]
                        query &= ((table.level.belongs(level)) | \
                                  (table.level == None))
                    else:
                        query &= (table.level.belongs(level))
                else:
                    query &= (table.level == level)
            ok = db(query).select(table.id, limitby=(0, 1)).first()

        if not ok:
            raise ValidationError(translate(self.error_message))

        return value

# =============================================================================
class IS_PROCESSED_IMAGE(Validator):
    """
        Used by S3ImageCropWidget (cropping/scaling uploaded images),
        post-processes the results sent by the browser
    """

    def __init__(self,
                 field_name,
                 file_cb,
                 *,
                 error_message = "No image was specified!",
                 image_bounds = (300, 300),
                 upload_path = None,
                 ):
        """
            Args:
                field_name: the form field holding the uploaded image
                file_cb: callback that returns the file for this field
                error_message: alternative error message
                image_bounds: the boundaries for the processed image
                upload_path: upload path for the image
        """

        self.field_name = field_name
        self.file_cb = file_cb
        self.error_message = error_message
        self.image_bounds = image_bounds
        self.upload_path = upload_path

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validator

            Args:
                value: the input value (uploaded image)
                record_id: the current record ID (unused, for API compatibility)

            Returns:
                the processed image as Storage(filename, file),
                or None if the processing happens async
        """

        if current.response.s3.bulk:
            # Pointless in imports
            return value

        request = current.request

        if request.env.request_method == "GET":
            return value

        post_vars = request.post_vars

        # If there's a newly uploaded file, accept it. It'll be processed in
        # the update form.
        # NOTE: A FieldStorage with data evaluates as False (odd!)
        uploaded_image = post_vars.get(self.field_name)
        if uploaded_image not in (b"", None):
            return uploaded_image

        cropped_image = post_vars.get("imagecrop-data")
        uploaded_image = self.file_cb()

        if not (cropped_image or uploaded_image):
            raise ValidationError(translate(self.error_message))

        # Decode the base64-encoded image from the client side image crop
        # process, if that worked
        if cropped_image:
            import base64

            metadata, cropped_image = cropped_image.rsplit(",", 1)
            #filename, datatype, enctype = metadata.split(";")
            filename = metadata.rsplit(";", 2)[0]

            f = Storage()
            f.filename = uuid4().hex + filename
            f.file = BytesIO(base64.b64decode(cropped_image))

            return f

        # Crop the image, if we've got the crop points
        points = post_vars.get("imagecrop-points")
        if points and uploaded_image:
            import os
            points = [float(p) for p in points.split(",")]

            if not self.upload_path:
                path = os.path.join(request.folder,
                                    "uploads",
                                    "images",
                                    uploaded_image,
                                    )
            else:
                path = os.path.join(self.upload_path,
                                    uploaded_image,
                                    )

            current.s3task.run_async("crop_image",
                            args = [path] + points + [self.image_bounds[0]])

        return uploaded_image

# =============================================================================
class IS_UTC_OFFSET(Validator):
    """ Validate a string as UTC offset expression """

    def __init__(self, error_message="invalid UTC offset!"):
        """
            Args:
                error_message: alternative error message
        """

        self.error_message = error_message

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validator

            Args:
                value: the input value
                record_id: the current record ID (unused, for API compatibility)

            Returns:
                the UTC offset as string +HHMM
        """

        if value and isinstance(value, str):

            offset = S3DateTime.get_offset_value(value)
            if offset is not None:
                hours, seconds = divmod(abs(offset), 3600)
                minutes = int(seconds / 60)
                sign = "-" if offset < 0 else "+"
                return "%s%02d%02d" % (sign, hours, minutes)

        raise ValidationError(translate(self.error_message))

# =============================================================================
class IS_UTC_DATETIME(Validator):
    """
        Validates a given date/time and returns it as timezone-naive
        datetime object in UTC. Accepted input types are strings (in
        local format), datetime.datetime and datetime.date.

        Example:
            - INPUT(_type="text", _name="name", requires=IS_UTC_DATETIME())

        Notes:
            - a date/time string must be in local format, and can have
              an optional trailing UTC offset specified as +/-HHMM
              (+ for eastern, - for western timezones)
            - dates stretch 8 hours West and 16 hours East of the current
              time zone, i.e. the most Eastern timezones are on the next
              day.
    """

    def __init__(self, *,
                 format = None,
                 error_message = None,
                 offset_error = None,
                 calendar = None,
                 minimum = None,
                 maximum = None,
                 ):
        """
            Args:
                format: strptime/strftime format template string, for
                        directives refer to your strptime implementation
                error_message: error message for invalid date/times
                offset_error: error message for invalid UTC offset
                calendar: calendar to use for string evaluation, defaults
                          to current.calendar
                minimum: the minimum acceptable date/time
                maximum: the maximum acceptable date/time
        """

        if format is None:
            self.format = str(current.deployment_settings.get_L10n_datetime_format())
        else:
            self.format = str(format)

        if isinstance(calendar, str):
            # Instantiate calendar by name
            from .calendar import S3Calendar
            calendar = S3Calendar(calendar)
        elif calendar == None:
            calendar = current.calendar
        self.calendar = calendar

        self.minimum = minimum
        self.maximum = maximum

        # Default error messages
        T = current.T
        if error_message is None:
            if minimum is None and maximum is None:
                error_message = T("Date/Time is required!")
            elif minimum is None:
                error_message = T("Date/Time must be %(max)s or earlier!")
            elif maximum is None:
                error_message = T("Date/Time must be %(min)s or later!")
            else:
                error_message = T("Date/Time must be between %(min)s and %(max)s!")
        if offset_error is None:
            offset_error = T("Invalid UTC offset!")

        # Localized minimum/maximum
        mindt = self.formatter(minimum) if minimum else ""
        maxdt = self.formatter(maximum) if maximum else ""

        # Store error messages
        self.error_message = error_message % {"min": mindt, "max": maxdt}
        self.offset_error = offset_error

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validator

            Args:
                value: the input value
                record_id: the current record ID (unused, for API compatibility)

            Returns:
                the corresponding UTC datetime, timezone-naive
        """

        if isinstance(value, str):

            val = value.strip()

            # Split date/time and UTC offset
            if len(val) > 5 and val[-5] in ("+", "-") and val[-4:].isdigit():
                dtstr, utc_offset = val[0:-5].strip(), val[-5:]
            else:
                dtstr, utc_offset = val, None

            # Convert into datetime object
            dt = self.calendar.parse_datetime(dtstr,
                                              dtfmt = self.format,
                                              local = True,
                                              )
            if dt is None:
                # Try parsing as date
                dt_ = self.calendar.parse_date(dtstr)
                if dt_ is None:
                    raise ValidationError(translate(self.error_message))
                dt = datetime.datetime.combine(dt_, datetime.datetime.min.time())
        elif isinstance(value, datetime.datetime):
            dt = value
            utc_offset = None
        elif isinstance(value, datetime.date):
            # Default to 8:00 hours in the current timezone
            dt = datetime.datetime.combine(value, datetime.time(8, 0, 0))
            utc_offset = None
        else:
            # Invalid type
            raise ValidationError(translate(self.error_message))

        # Convert to UTC and make tz-naive
        if not dt.tzinfo and utc_offset:
            offset = S3DateTime.get_offset_value(utc_offset)
            if not -86340 < offset < 86340:
                raise ValidationError(translate(self.offset_error))
            offset = datetime.timedelta(seconds=offset)
            dt_utc = (dt - offset).replace(tzinfo=None)
        else:
            dt_utc = S3DateTime.to_utc(dt)

        # Validate
        if self.minimum and dt_utc < self.minimum or \
           self.maximum and dt_utc > self.maximum:
            raise ValidationError(translate(self.error_message))

        return dt_utc

    # -------------------------------------------------------------------------
    def formatter(self, value):
        """
            Format a datetime as string.

            Args:
                value: the value (datetime)

            Returns:
                the corresponding string representation, in local
                timezone and format
        """

        if not value:
            return current.messages["NONE"]

        return self.calendar.format_datetime(S3DateTime.to_local(value),
                                             dtfmt = self.format,
                                             local = True,
                                             )

# =============================================================================
class IS_UTC_DATE(IS_UTC_DATETIME):
    """
        Validates a given date and returns the corresponding datetime.date
        object in UTC. Accepted input types are strings (in local format),
        datetime.datetime and datetime.date.

        Example:
            - INPUT(_type="text", _name="name", requires=IS_UTC_DATE())

        Note:
            dates stretch 8 hours West and 16 hours East of the current
            time zone, i.e. the most Eastern timezones are on the next day.
    """

    def __init__(self, *,
                 format = None,
                 error_message = None,
                 offset_error = None,
                 calendar = None,
                 minimum = None,
                 maximum = None,
                 ):
        """
            Args:
                format: strptime/strftime format template string, for
                        directives refer to your strptime implementation
                error_message: error message for invalid date/times
                offset_error: error message for invalid UTC offset
                calendar: calendar to use for string evaluation, defaults
                          to current.calendar
                minimum: the minimum acceptable date (datetime.date)
                maximum: the maximum acceptable date (datetime.date)
        """

        super().__init__(format = format,
                         error_message = error_message,
                         offset_error = offset_error,
                         calendar = calendar,
                         minimum = minimum,
                         maximum = maximum,
                         )

        if format is None:
            self.format = str(current.deployment_settings.get_L10n_date_format())

        # Default error messages
        T = current.T
        if error_message is None:
            if minimum is None and maximum is None:
                error_message = T("Date is required!")
            elif minimum is None:
                error_message = T("Date must be %(max)s or earlier!")
            elif maximum is None:
                error_message = T("Date must be %(min)s or later!")
            else:
                error_message = T("Date must be between %(min)s and %(max)s!")

        # Localized minimum/maximum
        mindt = self.formatter(minimum) if minimum else ""
        maxdt = self.formatter(maximum) if maximum else ""

        # Store error messages
        self.error_message = error_message % {"min": mindt, "max": maxdt}

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validator

            Args:
                value: the input value
                record_id: the current record ID (unused, for API compatibility)

            Returns:
                the corresponding UTC date
        """

        is_datetime = False

        if isinstance(value, str):
            # Convert into date object
            dt = self.calendar.parse_date(value.strip(),
                                          dtfmt = self.format,
                                          local = True,
                                          )
            if dt is None:
                raise ValidationError(translate(self.error_message))
        elif isinstance(value, datetime.datetime):
            dt = value
            is_datetime = True
        elif isinstance(value, datetime.date):
            # Default to 0:00 hours in the current timezone
            dt = value
        else:
            # Invalid type
            raise ValidationError(translate(self.error_message))

        # Convert to UTC
        if is_datetime:
            dt_utc = S3DateTime.to_utc(dt)
        else:
            # Convert to standard time 08:00 hours
            dt = datetime.datetime.combine(dt, datetime.time(8, 0, 0))
            dt_utc = S3DateTime.to_utc(dt)
        dt_utc = dt_utc.date()

        # Validate
        if self.minimum and dt_utc < self.minimum or \
           self.maximum and dt_utc > self.maximum:
            raise ValidationError(translate(self.error_message))

        return dt_utc

    # -------------------------------------------------------------------------
    def formatter(self, value):
        """
            Format a date as string.

            Args:
                value: the value (date)

            Returns:
                the corresponding string representation
        """

        if not value:
            return current.messages["NONE"]

        return self.calendar.format_date(S3DateTime.to_local(value),
                                         dtfmt = self.format,
                                         local = True,
                                         )

# =============================================================================
class IS_AVAILABLE_QUANTITY(Validator):
    """
        For Inventory module, check that quantity added to a shipment
        is available in the warehouse stock
    """

    def __init__(self, inv_item_id, item_pack_id):
        """
            Args:
                inv_item_id: the inventory item ID to check against
                item_pack_id: the shipment pack ID
        """

        self.inv_item_id = inv_item_id
        self.item_pack_id = item_pack_id

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validator

            Args:
                value: the input value (new track item quantity)
                record_id: the current record ID (track item)

            Returns:
                the value
        """

        db = current.db
        args = current.request.args

        track_quantity = 0

        track_item_id = record_id
        if args[1] == "track_item" and len(args) > 2:
            track_item_id = args[2]

        if track_item_id:
            # Check if new quantity exceeds quantity already tracked
            ttable = current.s3db.inv_track_item
            query = (ttable.id == track_item_id)
            track_record = db(query).select(ttable.quantity,
                                            limitby = (0, 1),
                                            ).first()
            track_quantity = track_record.quantity
            if track_quantity >= float(value):
                # Quantity reduced or unchanged, no need to re-validate
                return value

        error = None

        # Get the inventory item
        query = (db.inv_inv_item.id == self.inv_item_id) & \
                (db.inv_inv_item.item_pack_id == db.supply_item_pack.id)
        inv_item_record = db(query).select(db.inv_inv_item.quantity,
                                           db.supply_item_pack.quantity,
                                           db.supply_item_pack.name,
                                           limitby = (0, 1),
                                           ).first() # @todo: this should be a virtual field
        if not inv_item_record:
            error = "Inventory item not found"

        elif value:
            # Compute the quantity to be added
            query = (db.supply_item_pack.id == self.item_pack_id)
            pack = db(query).select(db.supply_item_pack.quantity,
                                    limitby=(0, 1),
                                    ).first()
            send_quantity = (float(value) - track_quantity) * pack.quantity

            # Compute the quantity in stock
            inv_quantity = inv_item_record.inv_inv_item.quantity * \
                           inv_item_record.supply_item_pack.quantity

            if send_quantity > inv_quantity:
                error = "Only %s %s (%s) in the Warehouse Stock." % \
                            (inv_quantity,
                             inv_item_record.supply_item_pack.name,
                             inv_item_record.supply_item_pack.quantity,
                             )
        else:
            error = "Invalid Quantity"

        if error:
            raise ValidationError(translate(error))

        return value

# =============================================================================
class IS_IN_SET_LAZY(Validator):
    """
        Like IS_IN_SET but with options obtained from a supplied function.
    """

    def __init__(self,
                 theset_fn,
                 represent = None, *,
                 error_message = "value not allowed",
                 multiple = False,
                 zero = "",
                 sort = False,
                 ):
        """
            Args:
                theset_fn: a callable that produces the set
                represent: representation function for items
                           in the set
                error_message: alternative error message
                multiple: allow multiple-selection
                zero: include an empty-option (label of empty-option)
                sort: alpha-sort the options by their labels
        """

        self.multiple = multiple
        if not callable(theset_fn):
            raise TypeError("Argument must be a callable.")

        self.theset_fn = theset_fn
        self.represent = represent

        self.error_message = error_message
        self.zero = zero
        self.sort = sort

        self.theset = None
        self.labels = None

    # -------------------------------------------------------------------------
    def _make_theset(self):
        """
            Generate the set

            Returns:
                list of items
        """

        theset = self.theset_fn()
        if theset:
            if isinstance(theset, dict):
                self.theset = [str(item) for item in theset]
                self.labels = list(theset.values())
            elif isinstance(theset, (tuple, list)):  # @ToDo: Can this be a Rows?
                if isinstance(theset[0], (tuple, list)) and len(theset[0])==2:
                    self.theset = [str(item) for item, label in theset]
                    self.labels = [str(label) for item, label in theset]
                else:
                    self.theset = [str(item) for item in theset]
                    represent = self.represent
                    if represent:
                        self.labels = [represent(item) for item in theset]
            else:
                self.theset = theset
        else:
            self.theset = []

    # -------------------------------------------------------------------------
    def options(self, zero=True):
        """
            Produce the options for a selector

            Args:
                zero: override for self.zero

            Returns:
                list of tuples (option, representation)
        """

        if not self.theset:
            self._make_theset()

        if not self.labels:
            items = [(k, k) for (i, k) in enumerate(self.theset)]
        else:
            items = [(k, self.labels[i]) for (i, k) in enumerate(self.theset)]
        if self.sort:
            items.sort(options_sorter)
        if zero and not self.zero is None and not self.multiple:
            items.insert(0, ("", self.zero))
        return items

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validator

            Args:
                value: the input value
                record_id: the current record ID (unused, for API compatiblity)

            Returns:
                the value
        """

        if not self.theset:
            self._make_theset()

        multiple = self.multiple
        if multiple:
            if isinstance(value, str):
                values = [value]
            elif isinstance(value, (tuple, list)):
                values = value
            elif not value:
                values = []
        else:
            values = [value]

        failures = [x for x in values if not x in self.theset]
        if failures and self.theset:
            if multiple and value in (None, ""):
                return []
            raise ValidationError(translate(self.error_message))

        if multiple:
            if isinstance(multiple, (tuple, list)) and \
               not multiple[0] <= len(values) < multiple[1]:
                raise ValidationError(translate(self.error_message))
            return values

        return value

# =============================================================================
class IS_PERSON_GENDER(IS_IN_SET):
    """
        Special validator for pr_person.gender and other fields
        referring to s3db.pr_gender_opts: accepts the Other-option ("O")
        even if it is not in the selectable set.
    """

    def validate(self, value, record_id=None):
        """
            Validator

            Args:
                value: the input value
                record_id: the current record ID (unused, for API compatibility)

            Returns:
                the gender key (s3db.pr_gender_opts)
        """

        if value == 4:
            # 4 = other, always accepted even if hidden
            return value

        return super().validate(value)

# =============================================================================
# Phone number patterns
#
PHONE_NUMBER_PATTERN = r"\+?\s*[\s\-\.\(\)\d]+(?:(?: x| ext)\s?\d{1,5})?"

# TODO Code that should only have a single number should
#      use IS_PHONE_NUMBER_SINGLE explicitly. Check what
#      messaging assumes.
SINGLE_PHONE_NUMBER_PATTERN = "%s$" % PHONE_NUMBER_PATTERN

# Multiple phone numbers can be separated by comma, slash, semi-colon.
# (Semi-colon appears in Brazil OSM data.)
# TODO Need to beware of separators used inside phone numbers
#      (e.g. 555-1212, ext 9), so may need fancier validation
#      if we see that.
# TODO Add tooltip giving list syntax, and warning against above.
#      (Current use is in importing OSM files, so isn't interactive.)
MULTI_PHONE_NUMBER_PATTERN = r"%s(\s*(,|/|;)\s*%s)*$" % (PHONE_NUMBER_PATTERN,
                                                         PHONE_NUMBER_PATTERN)

# -----------------------------------------------------------------------------
class IS_PHONE_NUMBER_SINGLE(Validator):
    """
        Validator for single phone numbers with option to
        enforce E.123 international notation (with leading +
        and no punctuation or spaces).
    """

    def __init__(self,
                 international = False,
                 error_message = None,
                 ):
        """
            Args:
                international: enforce E.123 international notation,
                               no effect if turned off globally in
                               deployment settings
                error_message: alternative error message
        """

        self.international = international
        self.error_message = error_message

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validation of a value

            Args:
                value: the phone number

            Returns:
                the phone number, with international=True, the phone number
                returned is converted into E.123 international notation.
        """

        error = False

        if isinstance(value, str):
            value = value.strip()
            if value and value[0] == chr(8206):
                # Strip the LRM character
                value = value[1:]
            requires = IS_MATCH(SINGLE_PHONE_NUMBER_PATTERN)
            try:
                number = requires.validate(s3_str(value))
            except ValidationError:
                error = True
        else:
            error = True

        error_message = self.error_message
        if not error:
            if self.international and \
               current.deployment_settings \
                      .get_msg_require_international_phone_numbers():

                # Configure alternative error message
                if not error_message:
                    error_message = "Enter phone number in international format like +46783754957"

                # Require E.123 international format
                number = "".join(re.findall(r"[\d+]+", number))
                match = re.match(r"(\+)([1-9]\d+)$", number)
                #match = re.match("(\+|00|\+00)([1-9]\d+)$", number)

                if match:
                    number = "+%s" % match.groups()[1]
                    return number
            else:
                return number

        if not error_message:
            error_message = "Enter a valid phone number"

        raise ValidationError(translate(error_message))

# -----------------------------------------------------------------------------
class IS_PHONE_NUMBER_MULTI(Validator):
    """
        Validator for multiple phone numbers.
    """

    def __init__(self,
                 error_message = "Enter a valid phone number",
                 ):
        """
            Args:
                error_message: alternative error message
        """

        self.error_message = error_message

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validator

            Args:
                value: the value

            Returns:
                the phone number
        """

        value = value.strip()
        if value == "":
            # e.g. s3_mark_required test
            raise ValidationError(translate(self.error_message))
        if value[0] == chr(8206):
            # Strip the LRM character
            value = value[1:]
        number = s3_str(value)

        requires = IS_MATCH(MULTI_PHONE_NUMBER_PATTERN)
        try:
            number = requires.validate(s3_str(value))
        except ValidationError as e:
            raise ValidationError(translate(self.error_message)) from e

        return number

# =============================================================================
class IS_DYNAMIC_FIELDNAME(Validator):
    """ Validator for field names in dynamic tables """

    PATTERN = re.compile("^[a-z]+[a-z0-9_]*$")

    def __init__(self,
                 error_message = "Invalid field name",
                 ):
        """
            Args:
                error_message: alternative error message
        """

        self.error_message = error_message

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validator

            Args:
                value: the value

            Returns:
                the field name
        """

        if value:

            name = str(value).lower().strip()

            from ..model import s3_all_meta_field_names

            if name != "id" and \
               name not in s3_all_meta_field_names() and \
               self.PATTERN.match(name):
                return name

        raise ValidationError(translate(self.error_message))

# =============================================================================
class IS_DYNAMIC_FIELDTYPE(Validator):
    """ Validator for field types in dynamic tables """

    SUPPORTED_TYPES = ("boolean",
                       "date",
                       "datetime",
                       "double",
                       "integer",
                       "reference",
                       "string",
                       "text",
                       "upload",
                       "json",
                       "list:integer",
                       "list:string",
                       )

    def __init__(self,
                 error_message = "Unsupported field type",
                 ):
        """
            Args:
                error_message: the error message for invalid values
        """

        self.error_message = error_message

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validation of a value

            Args:
                value: the value
                record_id: the current record ID (unused, for API compatibility)

            Returns:
                the field type (string)
        """

        if value:

            field_type = str(value).lower().strip()

            items = field_type.split(" ")
            base_type = items[0]

            if base_type == "reference":

                # Verify that referenced table is specified and exists
                if len(items) > 1:
                    ktablename = items[1].split(".")[0]
                    ktable = current.s3db.table(ktablename, db_only=True)
                    if ktable:
                        return field_type

            elif base_type in self.SUPPORTED_TYPES:
                return field_type

        raise ValidationError(self.error_message)

# =============================================================================
class IS_ISO639_2_LANGUAGE_CODE(IS_IN_SET):
    """
        Validate ISO639-2 Alpha-2/Alpha-3 language codes
    """

    def __init__(self, *,
                 error_message = "Invalid language code",
                 multiple = False,
                 select = DEFAULT,
                 sort = False,
                 translate = False,
                 zero = "",
                 ):
        """
            Args:
                error_message: alternative error message
                multiple: allow selection of multiple options
                select: dict or code/tuple-list of options for the
                        selector, defaults to settings.L10n.languages,
                        set explicitly to None to allow all languages
                sort: sort options in selector
                translate: translate the language options into
                           the current UI language
                zero: use this label for the empty-option (default="")
        """

        super().__init__(self.language_codes(),
                         error_message = error_message,
                         multiple = multiple,
                         zero = zero,
                         sort = sort,
                         )

        if select is DEFAULT:
            self._select = current.deployment_settings.get_L10n_languages()
        else:
            self._select = select

        self.translate = translate

    # -------------------------------------------------------------------------
    def options(self, zero=True):
        """
            Get the options for the selector. This could be only a subset
            of all valid options (self._select), therefore overriding
            superclass function here.

            Args:
                zero: include an empty-option (with self.zero as label)

            Returns:
                list of tuples (code, representation)
        """

        language_codes = self.language_codes(mis=False)

        translate = self.translate
        T = current.T

        selection = self._select
        if selection:
            language_codes_dict = dict(language_codes)
            if isinstance(selection, (list, tuple)):
                selection = self.subset(language_codes_dict, selection)
            items = ((k, (T(v) if translate else v))
                     for k, v in selection.items()
                     if k != "mis" and k in language_codes_dict
                     )
        else:
            if translate:
                items = ((k, T(v)) for k, v in language_codes)
            else:
                items = language_codes

        if self.sort:
            items = sorted(items, key=lambda s: s3_str(s[1]).lower())
        else:
            items = list(items)

        if zero and self.zero is not None and not self.multiple:
            items.insert(0, ("", self.zero))

        # Miscellaneous always as last option
        items.append(("mis", (T("Miscellaneous") if translate else "Miscellaneous")))

        return items

    # -------------------------------------------------------------------------
    @staticmethod
    def subset(languages, selection):
        """
            Converts a list|tuple of languages into a dict {code: name},
            permitting both languages codes or tuples (code, name) as
            list elements

            Args:
                languages: the complete language dict (from .language_codes)
                selection: the selection to determine the subset

            Returns:
                a dict {code: language}
        """

        subset = []
        append = subset.append

        for l in selection:
            if isinstance(l, str):
                name = languages.get(l)
                if name:
                    append((l, name))
            else:
                append(l)

        return dict(subset)

    # -------------------------------------------------------------------------
    def represent(self, code):
        """
            Represent a language code by language name, uses the
            representation from deployment_settings if available
            (to allow overrides).

            Args:
                code: the language code

            Returns:
                the language name
        """

        if not code:
            return current.messages["NONE"]

        l10n_languages = current.deployment_settings.get_L10n_languages()
        name = l10n_languages.get(code)
        if not name:
            name = dict(self.language_codes()).get(code.split("-")[0])
            if name is None:
                return current.messages.UNKNOWN_OPT

        if self.translate:
            name = current.T(name)

        return name

    # -------------------------------------------------------------------------
    @classmethod
    def represent_local(cls, code):
        """
            Represent a language code by the name of the language in that
            language. e.g. for Use in a Language dropdown

            Args:
                code: the language code

            Returns:
                the language name, translated to that language
        """

        if not code:
            return current.messages["NONE"]

        l10n_languages = current.deployment_settings.get_L10n_languages()
        name = l10n_languages.get(code)
        if not name:
            name = dict(cls.language_codes()).get(code.split("-")[0])
            if name is None:
                return current.messages.UNKNOWN_OPT

        T = current.T
        name = s3_str(T(name, language=code))

        return name

    # -------------------------------------------------------------------------
    @staticmethod
    def language_codes(mis=True):
        """
            Returns a list of tuples of ISO639-1 alpha-2 language
            codes, can also be used to look up the language name

            Args:
                mis: include the "Miscellaneous" option

            Just the subset which are useful for Translations
            - 2 letter code preferred, 3-letter code where none exists,
              no 'families' or Old
        """

        lang = [#("aar", "Afar"),
                ("aa", "Afar"),
                #("abk", "Abkhazian"),
                ("ab", "Abkhazian"),
                ("ace", "Achinese"),
                ("ach", "Acoli"),
                ("ada", "Adangme"),
                ("ady", "Adyghe; Adygei"),
                #("afa", "Afro-Asiatic languages"),
                #("afh", "Afrihili"),
                #("afr", "Afrikaans"),
                ("af", "Afrikaans"),
                ("ain", "Ainu"),
                #("aka", "Akan"),
                ("ak", "Akan"),
                #("akk", "Akkadian"),
                #("alb", "Albanian"),
                ("sq", "Albanian"),
                ("ale", "Aleut"),
                #("alg", "Algonquian languages"),
                ("alt", "Southern Altai"),
                #("amh", "Amharic"),
                ("am", "Amharic"),
                #("ang", "English, Old (ca.450-1100)"),
                ("anp", "Angika"),
                #("apa", "Apache languages"),
                #("ara", "Arabic"),
                ("ar", "Arabic"),
                #("arc", "Official Aramaic (700-300 BCE); Imperial Aramaic (700-300 BCE)"),
                #("arg", "Aragonese"),
                ("an", "Aragonese"),
                #("arm", "Armenian"),
                ("hy", "Armenian"),
                ("arn", "Mapudungun; Mapuche"),
                ("arp", "Arapaho"),
                #("art", "Artificial languages"),
                ("arw", "Arawak"),
                #("asm", "Assamese"),
                ("as", "Assamese"),
                ("ast", "Asturian; Bable; Leonese; Asturleonese"),
                #("ath", "Athapascan languages"),
                #("aus", "Australian languages"),
                #("ava", "Avaric"),
                ("av", "Avaric"),
                #("ave", "Avestan"),
                #("ae", "Avestan"),
                ("awa", "Awadhi"),
                #("aym", "Aymara"),
                ("ay", "Aymara"),
                #("aze", "Azerbaijani"),
                ("az", "Azerbaijani"),
                #("bad", "Banda languages"),
                #("bai", "Bamileke languages"),
                #("bak", "Bashkir"),
                ("ba", "Bashkir"),
                ("bal", "Baluchi"),
                #("bam", "Bambara"),
                ("bm", "Bambara"),
                ("ban", "Balinese"),
                #("baq", "Basque"),
                ("eu", "Basque"),
                ("bas", "Basa"),
                #("bat", "Baltic languages"),
                ("bej", "Beja; Bedawiyet"),
                #("bel", "Belarusian"),
                ("be", "Belarusian"),
                ("bem", "Bemba"),
                #("ben", "Bengali"),
                ("bn", "Bengali"),
                #("ber", "Berber languages"),
                ("bho", "Bhojpuri"),
                #("bih", "Bihari languages"),
                #("bh", "Bihari languages"),
                ("bik", "Bikol"),
                ("bin", "Bini; Edo"),
                #("bis", "Bislama"),
                ("bi", "Bislama"),
                ("bla", "Siksika"),
                #("bnt", "Bantu (Other)"),
                #("bos", "Bosnian"),
                ("bs", "Bosnian"),
                ("bra", "Braj"),
                #("bre", "Breton"),
                ("br", "Breton"),
                #("btk", "Batak languages"),
                ("bua", "Buriat"),
                ("bug", "Buginese"),
                #("bul", "Bulgarian"),
                ("bg", "Bulgarian"),
                #("bur", "Burmese"),
                ("my", "Burmese"),
                ("byn", "Blin; Bilin"),
                ("cad", "Caddo"),
                #("cai", "Central American Indian languages"),
                ("car", "Galibi Carib"),
                #("cat", "Catalan; Valencian"),
                ("ca", "Catalan; Valencian"),
                #("cau", "Caucasian languages"),
                ("ceb", "Cebuano"),
                #("cel", "Celtic languages"),
                #("cha", "Chamorro"),
                ("ch", "Chamorro"),
                #("chb", "Chibcha"),
                #("che", "Chechen"),
                ("ce", "Chechen"),
                #("chg", "Chagatai"),
                #("chi", "Chinese"),
                ("zh", "Chinese"),
                ("chk", "Chuukese"),
                ("chm", "Mari"),
                ("chn", "Chinook jargon"),
                ("cho", "Choctaw"),
                ("chp", "Chipewyan; Dene Suline"),
                ("chr", "Cherokee"),
                #("chu", "Church Slavic; Old Slavonic; Church Slavonic; Old Bulgarian; Old Church Slavonic"),
                #("cu", "Church Slavic; Old Slavonic; Church Slavonic; Old Bulgarian; Old Church Slavonic"),
                #("chv", "Chuvash"),
                ("cv", "Chuvash"),
                ("chy", "Cheyenne"),
                #("cmc", "Chamic languages"),
                #("cop", "Coptic"),
                #("cor", "Cornish"),
                ("kw", "Cornish"),
                #("cos", "Corsican"),
                ("co", "Corsican"),
                #("cpe", "Creoles and pidgins, English based"),
                #("cpf", "Creoles and pidgins, French-based"),
                #("cpp", "Creoles and pidgins, Portuguese-based"),
                #("cre", "Cree"),
                ("cr", "Cree"),
                ("crh", "Crimean Tatar; Crimean Turkish"),
                #("crp", "Creoles and pidgins"),
                ("csb", "Kashubian"),
                ("cus", "Cushitic languages"),
                #("cze", "Czech"),
                ("cs", "Czech"),
                ("dak", "Dakota"),
                #("dan", "Danish"),
                ("da", "Danish"),
                ("dar", "Dargwa"),
                #("day", "Land Dayak languages"),
                ("del", "Delaware"),
                ("den", "Slave (Athapascan)"),
                ("dgr", "Dogrib"),
                ("din", "Dinka"),
                #("div", "Divehi; Dhivehi; Maldivian"),
                ("dv", "Divehi; Dhivehi; Maldivian"),
                ("doi", "Dogri"),
                #("dra", "Dravidian languages"),
                ("dsb", "Lower Sorbian"),
                ("dua", "Duala"),
                #("dum", "Dutch, Middle (ca.1050-1350)"),
                #("dut", "Dutch; Flemish"),
                ("nl", "Dutch; Flemish"),
                ("dyu", "Dyula"),
                #("dzo", "Dzongkha"),
                ("dz", "Dzongkha"),
                ("efi", "Efik"),
                #("egy", "Egyptian (Ancient)"),
                ("eka", "Ekajuk"),
                #("elx", "Elamite"),
                #("eng", "English"),
                ("en", "English"),
                #("enm", "English, Middle (1100-1500)"),
                #("epo", "Esperanto"),
                #("eo", "Esperanto"),
                #("est", "Estonian"),
                ("et", "Estonian"),
                #("ewe", "Ewe"),
                ("ee", "Ewe"),
                ("ewo", "Ewondo"),
                ("fan", "Fang"),
                #("fao", "Faroese"),
                ("fo", "Faroese"),
                ("fat", "Fanti"),
                #("fij", "Fijian"),
                ("fj", "Fijian"),
                ("fil", "Filipino; Pilipino"),
                #("fin", "Finnish"),
                ("fi", "Finnish"),
                #("fiu", "Finno-Ugrian languages"),
                ("fon", "Fon"),
                #("fre", "French"),
                ("fr", "French"),
                #("frm", "French, Middle (ca.1400-1600)"),
                #("fro", "French, Old (842-ca.1400)"),
                ("frr", "Northern Frisian"),
                ("frs", "Eastern Frisian"),
                #("fry", "Western Frisian"),
                ("fy", "Western Frisian"),
                #("ful", "Fulah"),
                ("ff", "Fulah"),
                ("fur", "Friulian"),
                ("gaa", "Ga"),
                ("gay", "Gayo"),
                ("gba", "Gbaya"),
                #("gem", "Germanic languages"),
                #("geo", "Georgian"),
                ("ka", "Georgian"),
                #("ger", "German"),
                ("de", "German"),
                #("gez", "Geez"),
                ("gil", "Gilbertese"),
                #("gla", "Gaelic; Scottish Gaelic"),
                ("gd", "Gaelic; Scottish Gaelic"),
                #("gle", "Irish"),
                ("ga", "Irish"),
                #("glg", "Galician"),
                ("gl", "Galician"),
                #("glv", "Manx"),
                ("gv", "Manx"),
                #("gmh", "German, Middle High (ca.1050-1500)"),
                #("goh", "German, Old High (ca.750-1050)"),
                ("gon", "Gondi"),
                ("gor", "Gorontalo"),
                #("got", "Gothic"),
                ("grb", "Grebo"),
                #("grc", "Greek, Ancient (to 1453)"),
                #("gre", "Greek, Modern (1453-)"),
                ("el", "Greek"), # "Greek, Modern (1453-)"
                #("grn", "Guarani"),
                ("gn", "Guarani"),
                ("gsw", "Swiss German; Alemannic; Alsatian"),
                #("guj", "Gujarati"),
                ("gu", "Gujarati"),
                ("gwi", "Gwich'in"),
                ("hai", "Haida"),
                #("hat", "Haitian; Haitian Creole"),
                ("ht", "Haitian; Haitian Creole"),
                #("hau", "Hausa"),
                ("ha", "Hausa"),
                ("haw", "Hawaiian"),
                #("heb", "Hebrew"),
                ("he", "Hebrew"),
                #("her", "Herero"),
                ("hz", "Herero"),
                ("hil", "Hiligaynon"),
                #("him", "Himachali languages; Western Pahari languages"),
                #("hin", "Hindi"),
                ("hi", "Hindi"),
                #("hit", "Hittite"),
                ("hmn", "Hmong; Mong"),
                #("hmo", "Hiri Motu"),
                ("ho", "Hiri Motu"),
                #("hrv", "Croatian"),
                ("hr", "Croatian"),
                ("hsb", "Upper Sorbian"),
                #("hun", "Hungarian"),
                ("hu", "Hungarian"),
                ("hup", "Hupa"),
                ("iba", "Iban"),
                #("ibo", "Igbo"),
                ("ig", "Igbo"),
                #("ice", "Icelandic"),
                ("is", "Icelandic"),
                #("ido", "Ido"),
                #("io", "Ido"),
                #("iii", "Sichuan Yi; Nuosu"),
                ("ii", "Sichuan Yi; Nuosu"),
                #("ijo", "Ijo languages"),
                #("iku", "Inuktitut"),
                ("iu", "Inuktitut"),
                #("ile", "Interlingue; Occidental"),
                #("ie", "Interlingue; Occidental"),
                ("ilo", "Iloko"),
                #("ina", "Interlingua (International Auxiliary Language Association)"),
                #("ia", "Interlingua (International Auxiliary Language Association)"),
                #("inc", "Indic languages"),
                #("ind", "Indonesian"),
                ("id", "Indonesian"),
                #("ine", "Indo-European languages"),
                ("inh", "Ingush"),
                #("ipk", "Inupiaq"),
                ("ik", "Inupiaq"),
                #("ira", "Iranian languages"),
                #("iro", "Iroquoian languages"),
                #("ita", "Italian"),
                ("it", "Italian"),
                #("jav", "Javanese"),
                ("jv", "Javanese"),
                #("jbo", "Lojban"),
                #("jpn", "Japanese"),
                ("ja", "Japanese"),
                #("jpr", "Judeo-Persian"),
                #("jrb", "Judeo-Arabic"),
                ("kaa", "Kara-Kalpak"),
                ("kab", "Kabyle"),
                ("kac", "Kachin; Jingpho"),
                #("kal", "Kalaallisut; Greenlandic"),
                ("kl", "Kalaallisut; Greenlandic"),
                ("kam", "Kamba"),
                #("kan", "Kannada"),
                ("kn", "Kannada"),
                #("kar", "Karen languages"),
                #("kas", "Kashmiri"),
                ("ks", "Kashmiri"),
                #("kau", "Kanuri"),
                ("kr", "Kanuri"),
                #("kaw", "Kawi"),
                #("kaz", "Kazakh"),
                ("kk", "Kazakh"),
                ("kbd", "Kabardian"),
                ("kha", "Khasi"),
                #("khi", "Khoisan languages"),
                #("khm", "Central Khmer"),
                ("km", "Central Khmer"),
                #("kho", "Khotanese; Sakan"),
                #("kik", "Kikuyu; Gikuyu"),
                ("ki", "Kikuyu; Gikuyu"),
                #("kin", "Kinyarwanda"),
                ("rw", "Kinyarwanda"),
                #("kir", "Kirghiz; Kyrgyz"),
                ("ky", "Kirghiz; Kyrgyz"),
                ("kmb", "Kimbundu"),
                ("kok", "Konkani"),
                #("kom", "Komi"),
                ("kv", "Komi"),
                #("kon", "Kongo"),
                ("kg", "Kongo"),
                #("kor", "Korean"),
                ("ko", "Korean"),
                ("kos", "Kosraean"),
                ("kpe", "Kpelle"),
                ("krc", "Karachay-Balkar"),
                ("krl", "Karelian"),
                #("kro", "Kru languages"),
                ("kru", "Kurukh"),
                #("kua", "Kuanyama; Kwanyama"),
                ("kj", "Kuanyama; Kwanyama"),
                ("kum", "Kumyk"),
                #("kur", "Kurdish"),
                ("ku", "Kurdish"),
                ("kut", "Kutenai"),
                ("lad", "Ladino"),
                ("lah", "Lahnda"),
                ("lam", "Lamba"),
                #("lao", "Lao"),
                ("lo", "Lao"),
                #("lat", "Latin"),
                #("la", "Latin"),
                #("lav", "Latvian"),
                ("lv", "Latvian"),
                ("lez", "Lezghian"),
                #("lim", "Limburgan; Limburger; Limburgish"),
                ("li", "Limburgan; Limburger; Limburgish"),
                #("lin", "Lingala"),
                ("ln", "Lingala"),
                #("lit", "Lithuanian"),
                ("lt", "Lithuanian"),
                ("lol", "Mongo"),
                ("loz", "Lozi"),
                #("ltz", "Luxembourgish; Letzeburgesch"),
                ("lb", "Luxembourgish; Letzeburgesch"),
                ("lua", "Luba-Lulua"),
                #("lub", "Luba-Katanga"),
                ("lu", "Luba-Katanga"),
                #("lug", "Ganda"),
                ("lg", "Ganda"),
                #("lui", "Luiseno"),
                ("lun", "Lunda"),
                ("luo", "Luo (Kenya and Tanzania)"),
                ("lus", "Lushai"),
                #("mac", "Macedonian"),
                ("mk", "Macedonian"),
                ("mad", "Madurese"),
                ("mag", "Magahi"),
                #("mah", "Marshallese"),
                ("mh", "Marshallese"),
                ("mai", "Maithili"),
                ("mak", "Makasar"),
                #("mal", "Malayalam"),
                ("ml", "Malayalam"),
                ("man", "Mandingo"),
                #("mao", "Maori"),
                ("mi", "Maori"),
                #("map", "Austronesian languages"),
                #("mar", "Marathi"),
                ("mr", "Marathi"),
                ("mas", "Masai"),
                #("may", "Malay"),
                ("ms", "Malay"),
                ("mdf", "Moksha"),
                ("mdr", "Mandar"),
                ("men", "Mende"),
                #("mga", "Irish, Middle (900-1200)"),
                ("mic", "Mi'kmaq; Micmac"),
                ("min", "Minangkabau"),
                #("mis", "Uncoded languages"),
                #("mkh", "Mon-Khmer languages"),
                #("mlg", "Malagasy"),
                ("mg", "Malagasy"), # Madagascar
                ("mlt", "Maltese"),
                ("mt", "Maltese"),
                ("mnc", "Manchu"),
                ("mni", "Manipuri"),
                #("mno", "Manobo languages"),
                ("moh", "Mohawk"),
                #("mon", "Mongolian"),
                ("mn", "Mongolian"),
                ("mos", "Mossi"),
                #("mul", "Multiple languages"),
                #("mun", "Munda languages"),
                ("mus", "Creek"),
                ("mwl", "Mirandese"),
                ("mwr", "Marwari"),
                #("myn", "Mayan languages"),
                ("myv", "Erzya"),
                #("nah", "Nahuatl languages"),
                #("nai", "North American Indian languages"),
                ("nap", "Neapolitan"),
                #("nau", "Nauru"),
                ("na", "Nauru"),
                #("nav", "Navajo; Navaho"),
                ("nv", "Navajo; Navaho"),
                #("nbl", "Ndebele, South; South Ndebele"),
                ("nr", "Ndebele, South; South Ndebele"),
                #("nde", "Ndebele, North; North Ndebele"),
                ("nd", "Ndebele, North; North Ndebele"),
                #("ndo", "Ndonga"),
                ("ng", "Ndonga"),
                ("nds", "Low German; Low Saxon; German, Low; Saxon, Low"),
                #("nep", "Nepali"),
                ("ne", "Nepali"),
                ("new", "Nepal Bhasa; Newari"),
                ("nia", "Nias"),
                #("nic", "Niger-Kordofanian languages"),
                ("niu", "Niuean"),
                #("nno", "Norwegian Nynorsk; Nynorsk, Norwegian"),
                ("nn", "Norwegian Nynorsk; Nynorsk, Norwegian"),
                #("nob", "Bokmål, Norwegian; Norwegian Bokmål"),
                ("nb", "Bokmål, Norwegian; Norwegian Bokmål"),
                ("nog", "Nogai"),
                #("non", "Norse, Old"),
                #("nor", "Norwegian"),
                ("no", "Norwegian"),
                ("nqo", "N'Ko"),
                ("nso", "Pedi; Sepedi; Northern Sotho"),
                #("nub", "Nubian languages"),
                #("nwc", "Classical Newari; Old Newari; Classical Nepal Bhasa"),
                #("nya", "Chichewa; Chewa; Nyanja"),
                ("ny", "Chichewa; Chewa; Nyanja"),
                ("nym", "Nyamwezi"),
                ("nyn", "Nyankole"),
                ("nyo", "Nyoro"),
                ("nzi", "Nzima"),
                #("oci", "Occitan (post 1500); Provençal"),
                ("oc", "Occitan (post 1500); Provençal"),
                #("oji", "Ojibwa"),
                ("oj", "Ojibwa"),
                #("ori", "Oriya"),
                ("or", "Oriya"),
                #("orm", "Oromo"),
                ("om", "Oromo"),
                ("osa", "Osage"),
                #("oss", "Ossetian; Ossetic"),
                ("os", "Ossetian; Ossetic"),
                #("ota", "Turkish, Ottoman (1500-1928)"),
                #("oto", "Otomian languages"),
                #("paa", "Papuan languages"),
                ("pag", "Pangasinan"),
                #("pal", "Pahlavi"),
                ("pam", "Pampanga; Kapampangan"),
                #("pan", "Panjabi; Punjabi"),
                ("pa", "Panjabi; Punjabi"),
                ("pap", "Papiamento"),
                ("pau", "Palauan"),
                #("peo", "Persian, Old (ca.600-400 B.C.)"),
                #("per", "Persian"),
                ("fa", "Persian"),
                #("phi", "Philippine languages"),
                #("phn", "Phoenician"),
                #("pli", "Pali"),
                #("pi", "Pali"),
                #("pol", "Polish"),
                ("pl", "Polish"),
                ("pon", "Pohnpeian"),
                #("por", "Portuguese"),
                ("pt", "Portuguese"),
                #("pra", "Prakrit languages"),
                #("pro", "Provençal, Old (to 1500)"),
                ("prs", "Dari"),
                #("pus", "Pushto; Pashto"),
                ("ps", "Pushto; Pashto"),
                #("qaa-qtz", "Reserved for local use"),
                #("que", "Quechua"),
                ("qu", "Quechua"),
                ("raj", "Rajasthani"),
                ("rap", "Rapanui"),
                ("rar", "Rarotongan; Cook Islands Maori"),
                #("roa", "Romance languages"),
                #("roh", "Romansh"),
                ("rm", "Romansh"),
                ("rom", "Romany"),
                #("rum", "Romanian; Moldavian; Moldovan"),
                ("ro", "Romanian; Moldavian; Moldovan"),
                #("run", "Rundi"),
                ("rn", "Rundi"),
                ("rup", "Aromanian; Arumanian; Macedo-Romanian"),
                #("rus", "Russian"),
                ("ru", "Russian"),
                ("sad", "Sandawe"),
                #("sag", "Sango"),
                ("sg", "Sango"),
                ("sah", "Yakut"),
                #("sai", "South American Indian (Other)"),
                #("sal", "Salishan languages"),
                #("sam", "Samaritan Aramaic"),
                #("san", "Sanskrit"),
                #("sa", "Sanskrit"),
                ("sas", "Sasak"),
                ("sat", "Santali"),
                ("scn", "Sicilian"),
                ("sco", "Scots"),
                ("sel", "Selkup"),
                #("sem", "Semitic languages"),
                #("sga", "Irish, Old (to 900)"),
                ("sgn", "Sign Languages"),
                ("shn", "Shan"),
                ("sid", "Sidamo"),
                #("sin", "Sinhala; Sinhalese"),
                ("si", "Sinhala; Sinhalese"),
                #("sio", "Siouan languages"),
                #("sit", "Sino-Tibetan languages"),
                #("sla", "Slavic languages"),
                #("slo", "Slovak"),
                ("sk", "Slovak"),
                #("slv", "Slovenian"),
                ("sl", "Slovenian"),
                ("sma", "Southern Sami"),
                #("sme", "Northern Sami"),
                ("se", "Northern Sami"),
                #("smi", "Sami languages"),
                ("smj", "Lule Sami"),
                ("smn", "Inari Sami"),
                #("smo", "Samoan"),
                ("sm", "Samoan"),
                ("sms", "Skolt Sami"),
                #("sna", "Shona"),
                ("sn", "Shona"),
                #("snd", "Sindhi"),
                ("sd", "Sindhi"),
                ("snk", "Soninke"),
                #("sog", "Sogdian"),
                #("som", "Somali"),
                ("so", "Somali"),
                #("son", "Songhai languages"),
                #("sot", "Sotho, Southern"),
                ("st", "Sotho, Southern"), # Sesotho
                #("spa", "Spanish; Castilian"),
                ("es", "Spanish; Castilian"),
                #("srd", "Sardinian"),
                ("sc", "Sardinian"),
                ("srn", "Sranan Tongo"),
                #("srp", "Serbian"),
                ("sr", "Serbian"),
                ("srr", "Serer"),
                #("ssa", "Nilo-Saharan languages"),
                #("ssw", "Swati"),
                ("ss", "Swati"),
                ("suk", "Sukuma"),
                #("sun", "Sundanese"),
                ("su", "Sundanese"),
                ("sus", "Susu"),
                #("sux", "Sumerian"),
                #("swa", "Swahili"),
                ("sw", "Swahili"),
                #("swe", "Swedish"),
                ("sv", "Swedish"),
                #("syc", "Classical Syriac"),
                ("syr", "Syriac"),
                #("tah", "Tahitian"),
                ("ty", "Tahitian"),
                #("tai", "Tai languages"),
                #("tam", "Tamil"),
                ("ta", "Tamil"),
                #("tat", "Tatar"),
                ("tt", "Tatar"),
                #("tel", "Telugu"),
                ("te", "Telugu"),
                ("tem", "Timne"),
                ("ter", "Tereno"),
                ("tet", "Tetum"),
                #("tgk", "Tajik"),
                ("tg", "Tajik"),
                #("tgl", "Tagalog"),
                ("tl", "Tagalog"),
                #("tha", "Thai"),
                ("th", "Thai"),
                #("tib", "Tibetan"),
                ("bo", "Tibetan"),
                ("tig", "Tigre"),
                #("tir", "Tigrinya"),
                ("ti", "Tigrinya"),
                ("tiv", "Tiv"),
                ("tkl", "Tokelau"),
                #("tlh", "Klingon; tlhIngan-Hol"),
                ("tli", "Tlingit"),
                ("tmh", "Tamashek"),
                ("tog", "Tonga (Nyasa)"),
                #("ton", "Tonga (Tonga Islands)"),
                ("to", "Tonga (Tonga Islands)"),
                ("tpi", "Tok Pisin"),
                ("tsi", "Tsimshian"),
                #("tsn", "Tswana"),
                ("tn", "Tswana"),
                #("tso", "Tsonga"),
                ("ts", "Tsonga"),
                #("tuk", "Turkmen"),
                ("tk", "Turkmen"),
                ("tum", "Tumbuka"),
                #("tup", "Tupi languages"),
                #("tur", "Turkish"),
                ("tr", "Turkish"),
                #("tut", "Altaic languages"),
                ("tvl", "Tuvalu"),
                #("twi", "Twi"),
                ("tw", "Twi"),
                ("tyv", "Tuvinian"),
                ("udm", "Udmurt"),
                #("uga", "Ugaritic"),
                #("uig", "Uighur; Uyghur"),
                ("ug", "Uighur; Uyghur"),
                #("ukr", "Ukrainian"),
                ("uk", "Ukrainian"),
                ("umb", "Umbundu"),
                #("und", "Undetermined"),
                #("urd", "Urdu"),
                ("ur", "Urdu"),
                #("uzb", "Uzbek"),
                ("uz", "Uzbek"),
                ("vai", "Vai"),
                #("ven", "Venda"),
                ("ve", "Venda"),
                #("vie", "Vietnamese"),
                ("vi", "Vietnamese"),
                #("vol", "Volapük"),
                #("vo", "Volapük"),
                ("vot", "Votic"),
                #("wak", "Wakashan languages"),
                ("wal", "Walamo"),
                ("war", "Waray"),
                ("was", "Washo"),
                #("wel", "Welsh"),
                ("cy", "Welsh"),
                #("wen", "Sorbian languages"),
                #("wln", "Walloon"),
                ("wa", "Walloon"),
                #("wol", "Wolof"),
                ("wo", "Wolof"),
                ("xal", "Kalmyk; Oirat"),
                #("xho", "Xhosa"),
                ("xh", "Xhosa"),
                ("yao", "Yao"),
                ("yap", "Yapese"),
                #("yid", "Yiddish"),
                ("yi", "Yiddish"),
                #("yor", "Yoruba"),
                ("yo", "Yoruba"),
                #("ypk", "Yupik languages"),
                ("zap", "Zapotec"),
                #("zbl", "Blissymbols; Blissymbolics; Bliss"),
                ("zen", "Zenaga"),
                ("zgh", "Standard Moroccan Tamazight"),
                #("zha", "Zhuang; Chuang"),
                ("za", "Zhuang; Chuang"),
                #("znd", "Zande languages"),
                #("zul", "Zulu"),
                ("zu", "Zulu"),
                ("zun", "Zuni"),
                #("zxx", "No linguistic content; Not applicable"),
                ("zza", "Zaza; Dimili; Dimli; Kirdki; Kirmanjki; Zazaki"),
                ]

        settings = current.deployment_settings

        l10n_languages = settings.get_L10n_languages()
        lang += l10n_languages.items()

        extra_codes = settings.get_L10n_extra_codes()
        if extra_codes:
            lang += extra_codes
        if mis:
            lang.append(("mis", "Miscellaneous"))

        return list(set(lang)) # Remove duplicates

# =============================================================================
class IS_IBAN(Validator):
    """
        Validate IBAN International Bank Account Numbers (ISO 13616:2007)
    """

    # Valid country codes
    countries = {"AD", "AE", "AL", "AT", "AZ", "BA", "BE", "BG", "BH",
                 "BR", "CH", "CR", "CY", "CZ", "DE", "DK", "DO", "EE",
                 "ES", "FI", "FO", "FR", "GB", "GE", "GI", "GL", "GR",
                 "GT", "HR", "HU", "IE", "IL", "IS", "IT", "JO", "KW",
                 "KZ", "LB", "LC", "LI", "LT", "LU", "LV", "MC", "MD",
                 "ME", "MK", "MR", "MT", "MU", "NL", "NO", "PK", "PL",
                 "PS", "PT", "QA", "RO", "RS", "SA", "SC", "SE", "SI",
                 "SK", "SM", "ST", "TL", "TN", "TR", "UA", "VG", "XK",
                 }

    def __init__(self, error_message="Invalid IBAN"):
        """
            Args:
                error_message: alternative error message
        """

        self.error_message = error_message

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validate an International Bank Account Number (IBAN)

            Args:
                value: the IBAN as string (may contain blanks)
                record_id: the current record ID (unused, for API compatibility)

            Returns:
                the sanitized IBAN (without blanks)
        """

        if value is None:
            raise ValidationError(translate(self.error_message))

        # Sanitize
        iban = s3_str(value).strip().replace(" ", "").upper()

        # Pattern check
        m = IBAN_SCHEMA.match(iban)
        if not m:
            raise ValidationError(translate(self.error_message))

        # Country code check
        cc = m.group(1)
        if cc not in self.countries:
            raise ValidationError(translate(self.error_message))

        # Re-arrange and convert to numeric
        code = m.group(3) + cc + m.group(2)
        items = [c if c.isdigit() else str(ord(c) - 55) for c in code]
        iban_numeric = "".join(items)

        # Mod-97 validation of numeric code
        head, tail = iban_numeric[:2], iban_numeric[2:]
        while tail:
            head = "%02d" % (int(head + tail[:7]) % 97)
            tail = tail[7:]
        if int(head) != 1:
            raise ValidationError(translate(self.error_message))

        return iban

    # -------------------------------------------------------------------------
    @staticmethod
    def represent(value, row=None):
        """
            Format an IBAN as 4-character blocks, for better readability

            Args:
                value: the IBAN
                row: unused, for API compatibility

            Returns:
                the formatted IBAN
        """

        if not value:
            reprstr = "-"
        else:
            iban = s3_str(value).strip().replace(" ", "").upper()
            reprstr = " ".join(re.findall('..?.?.?', iban))
        return reprstr

# =============================================================================
class SKIP_VALIDATION(Validator):
    """
        Pseudo-validator that allows introspection of field options
        during GET, but does nothing during POST. Used for Ajax-validated
        inline-components to prevent them from throwing validation errors
        when the outer form gets submitted.
    """

    def __init__(self, other=None):
        """
            Args:
                other: the actual field validator

            Example:
                field.requires = SKIP_VALIDATION(field.requires)
        """

        if other and isinstance(other, (list, tuple)):
            other = other[0]
        self.other = other
        if other:
            if hasattr(other, "multiple"):
                self.multiple = other.multiple
            if hasattr(other, "options"):
                self.options = other.options
            if hasattr(other, "formatter"):
                self.formatter = other.formatter

    # -------------------------------------------------------------------------
    def validate(self, value, record_id=None):
        """
            Validation

            Args:
                value: the value
                record_id: the record ID (unused, for API compatibility)
        """

        other = self.other
        if current.request.env.request_method == "POST" or not other:
            return value
        if not isinstance(other, (list, tuple)):
            other = [other]
        for r in other:
            value = validator_caller(r, value, record_id)

        return value

    ## -------------------------------------------------------------------------
    #def __call__(self, value, record_id=None):
        #"""
            #Validation

            #Args:
                #value: the value
                #record_id: the record ID (unused, for API compatibility)
        #"""

        #other = self.other
        #if current.request.env.request_method == "POST" or not other:
            #return value, None
        #if not isinstance(other, (list, tuple)):
            #other = [other]
        #for r in other:
            #value, error = r(value)
            #if error:
                #return value, error
        #return value, None

# END =========================================================================
