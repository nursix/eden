"""
    Disease Tracking Models

    Copyright: 2014-2022 (c) Sahana Software Foundation

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

    TODO Extend to Vector Tracking for Dengue/Malaria
"""

__all__ = ("DiseaseDataModel",
           "DiseaseMonitoringModel",
           "DiseaseCertificateModel",
           "DiseaseCaseTrackingModel",
           "DiseaseContactTracingModel",
           "DiseaseStatsModel",
           "disease_rheader",
           )

import datetime
import json

from functools import reduce

from gluon import *
from gluon.storage import Storage

from ..core import *

# Monitoring upgrades {new_level:previous_levels}
MONITORING_UPGRADE = {"OBSERVATION": ("NONE",
                                      "FOLLOW-UP",
                                      ),
                      "DIAGNOSTICS": ("NONE",
                                      "OBSERVATION",
                                      "FOLLOW-UP",
                                      ),
                      "QUARANTINE": ("NONE",
                                     "OBSERVATION",
                                     "DIAGNOSTICS",
                                     "FOLLOW-UP",
                                     ),
                      }

# =============================================================================
class DiseaseDataModel(DataModel):

    names = ("disease_disease",
             "disease_disease_id",
             "disease_symptom",
             "disease_symptom_id",
             "disease_testing_device",
             "disease_testing_device_id",
             )

    def model(self):

        T = current.T
        db = current.db

        crud_strings = current.response.s3.crud_strings
        define_table = self.define_table

        # =====================================================================
        # Basic Disease Information
        #
        tablename = "disease_disease"
        define_table(tablename,
                     self.super_link("doc_id", "doc_entity"),
                     # @ToDo: Labels for i18n
                     Field("name",
                           requires = IS_NOT_EMPTY()
                           ),
                     Field("short_name"),
                     Field("acronym"),
                     Field("code",
                           label = T("ICD-10-CM Code"),
                           ),
                     Field("description", "text"),
                     Field("trace_period", "integer",
                           label = T("Trace Period before Symptom Debut (days)"),
                           ),
                     Field("watch_period", "integer",
                           label = T("Watch Period after Exposure (days)"),
                           ),
                     CommentsField(),
                     )

        represent = S3Represent(lookup=tablename)
        disease_id = FieldTemplate("disease_id", "reference %s" % tablename,
                                   label = T("Disease"),
                                   represent = represent,
                                   requires = IS_ONE_OF(db, "disease_disease.id",
                                                        represent,
                                                        ),
                                   sortby = "name",
                                   comment = PopupLink(f = "disease",
                                                       tooltip = T("Add a new disease to the catalog"),
                                                       ),
                                   )

        self.add_components(tablename,
                            disease_symptom = "disease_id",
                            )

        self.configure(tablename,
                       deduplicate = self.disease_duplicate,
                       super_entity = "doc_entity",
                       )

        # CRUD strings
        crud_strings[tablename] = Storage(
            label_create = T("Create Disease"),
            title_display = T("Disease Information"),
            title_list = T("Diseases"),
            title_update = T("Edit Disease Information"),
            title_upload = T("Import Disease Information"),
            label_list_button = T("List Diseases"),
            label_delete_button = T("Delete Disease Information"),
            msg_record_created = T("Disease Information added"),
            msg_record_modified = T("Disease Information updated"),
            msg_record_deleted = T("Disease Information deleted"),
            msg_list_empty = T("No Diseases currently registered"))

        # =====================================================================
        # Symptom Information
        #
        tablename = "disease_symptom"
        define_table(tablename,
                     disease_id(),
                     Field("name"),
                     Field("description",
                           label = T("Short Description"),
                           ),
                     Field("assessment",
                           label = T("Assessment method"),
                           ),
                     )

        # @todo: refine to include disease name?
        represent = S3Represent(lookup=tablename)
        symptom_id = FieldTemplate("symptom_id", "reference %s" % tablename,
                                   label = T("Symptom"),
                                   represent = represent,
                                   requires = IS_ONE_OF(db, "disease_symptom.id",
                                                        represent,
                                                        ),
                                   sortby = "name",
                                   )

        # CRUD strings
        crud_strings[tablename] = Storage(
            label_create = T("Add Symptom"),
            title_display = T("Symptom Information"),
            title_list = T("Symptoms"),
            title_update = T("Edit Symptom Information"),
            title_upload = T("Import Symptom Information"),
            label_list_button = T("List Symptoms"),
            label_delete_button = T("Delete Symptom Information"),
            msg_record_created = T("Symptom Information added"),
            msg_record_modified = T("Symptom Information updated"),
            msg_record_deleted = T("Symptom Information deleted"),
            msg_list_empty = T("No Symptom Information currently available"))

        # ---------------------------------------------------------------------
        # Testing device registry
        # - registry of approved testing devices for reference in e.g.
        #   diagnostics, certificates etc.
        #
        device_classes = {"RAT": T("Rapid Antigen Test"),
                          # to be extended
                          }

        tablename = "disease_testing_device"
        define_table(tablename,
                     disease_id(ondelete = "CASCADE",
                                comment = None,
                                ),
                     Field("name",
                           label = T("Name"),
                           requires = IS_NOT_EMPTY(),
                           ),
                     Field("code", length=64,
                           label = T("Code"),
                           requires = IS_EMPTY_OR(IS_LENGTH(64)),
                           ),
                     Field("device_class",
                           label = T("Device Class"),
                           requires = IS_IN_SET(device_classes,
                                                zero = None,
                                                ),
                           represent = represent_option(device_classes),
                           ),
                     Field("approved", "boolean",
                           default = True,
                           label = T("Approved##actionable"),
                           represent = s3_yes_no_represent,
                           ),
                     # The list of approved devices can be long, but not all
                     # of them are commonly available/in use - so can use this
                     # flag to reduce the list in selectors to what is practical:
                     Field("available", "boolean",
                           default = True,
                           label = T("Available"),
                           represent = s3_yes_no_represent,
                           ),
                     # Source would normally be a URI, but can also be a name
                     # or similar, activate in template if/as needed:
                     Field("source",
                           readable = False,
                           writable = False,
                           ),
                     CommentsField(),
                     )

        # Table configuration
        self.configure(tablename,
                       #onaccept = self.testing_device_onaccept,
                       )

        # CRUD Strings
        crud_strings[tablename] = Storage(
            label_create = T("Add Testing Device"),
            title_display = T("Testing Device Details"),
            title_list = T("Testing Devices"),
            title_update = T("Edit Testing Device"),
            label_list_button = T("List Testing Devices"),
            label_delete_button = T("Delete Testing Device"),
            msg_record_created = T("Testing Device created"),
            msg_record_modified = T("Testing Device updated"),
            msg_record_deleted = T("Testing Device deleted"),
            msg_list_empty = T("No Testing Devices currently registered"),
            )

        # Foreign Key Template
        represent = S3Represent(lookup=tablename)
        device_id = FieldTemplate("device_id", "reference %s" % tablename,
                                  label = T("Testing Device"),
                                  represent = represent,
                                  requires = IS_ONE_OF(db, "%s.id" % tablename,
                                                       represent,
                                                       filterby = "available",
                                                       filter_opts = [True],
                                                       ),
                                  sortby = "name",
                                  )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return {"disease_disease_id": disease_id,
                "disease_symptom_id": symptom_id,
                "disease_testing_device_id": device_id,
                }

    # -------------------------------------------------------------------------
    def defaults(self):
        """ Safe defaults for names in case the module is disabled """

        dummy = FieldTemplate.dummy

        return {"disease_disease_id": dummy("disease_id"),
                "disease_symptom_id": dummy("symptom_id"),
                "disease_testing_device_id": dummy("device_id"),
                }

    # -------------------------------------------------------------------------
    @staticmethod
    def disease_duplicate(item):
        """
            Disease import update detection

            Args:
                item: the import item
        """

        data = item.data
        code = data.get("code")
        name = data.get("name")

        table = item.table
        queries = []
        if code:
            queries.append((table.code == code))
        if name:
            queries.append((table.name == name))
        if queries:
            query = reduce(lambda x, y: x | y, queries)
        else:
            return

        rows = current.db(query).select(table.id,
                                        table.code,
                                        table.name)
        duplicate = None
        for row in rows:
            if code and row.code == code:
                duplicate = row.id
                break
            if name and row.name == name:
                duplicate = row.id
        if duplicate:
            item.id = duplicate
            item.method = item.METHOD.UPDATE

    # -------------------------------------------------------------------------
    @staticmethod
    def testing_device_onaccept(form):
        """
            Onaccept routine for testing devices
                - make sure only approved devices are available
        """

        form_vars = form.vars
        try:
            record_id = form_vars.id
        except AttributeError:
            record_id = None
        if not record_id:
            return

        # Get the record
        table = current.s3db.disease_testing_device
        query = (table.id == record_id)
        record = current.db(query).select(table.id,
                                          table.approved,
                                          table.available,
                                          limitby = (0, 1),
                                          ).first()
        if not record:
            return

        # If record is not approved, it must not be available either
        if record.available and not record.approved:
            record.update_record(available=False)

# =============================================================================
class DiseaseMonitoringModel(DataModel):
    """ Data Model for Disease Monitoring """

    names = ("disease_demographic",
             "disease_demographic_id",
             "disease_testing_report",
             "disease_testing_demographic",
             )

    def model(self):

        T = current.T

        db = current.db
        s3 = current.response.s3
        settings = current.deployment_settings

        crud_strings = s3.crud_strings

        define_table = self.define_table
        configure = self.configure

        # ---------------------------------------------------------------------
        # Demographics for disease monitoring/reporting
        # - e.g. age groups, vulnerable groups...
        #
        tablename = "disease_demographic"
        define_table(tablename,
                     Field("code", length=16, notnull=True, unique=True,
                           label = T("Code"),
                           requires = [IS_NOT_EMPTY(),
                                       IS_LENGTH(16, minsize=1),
                                       IS_NOT_ONE_OF(db,
                                                     "%s.code" % tablename,
                                                     ),
                                       ],
                           comment = DIV(_class = "tooltip",
                                         _title = "%s|%s" % (T("Code"),
                                                             T("A unique code for this demographic"),
                                                             ),
                                         ),
                           ),
                     Field("name",
                           label = T("Name"),
                           requires = IS_NOT_EMPTY(),
                           ),
                     Field("obsolete", "boolean",
                           default = False,
                           label = T("Obsolete"),
                           represent = s3_yes_no_represent,
                           ),
                     CommentsField(),
                     )

        # CRUD Strings
        crud_strings[tablename] = Storage(
            label_create = T("Add Demographic"),
            title_display = T("Demographic Details"),
            title_list = T("Demographics"),
            title_update = T("Edit Demographic"),
            label_list_button = T("List Demographics"),
            label_delete_button = T("Delete Demographic"),
            msg_record_created = T("Demographic added"),
            msg_record_modified = T("Demographic updated"),
            msg_record_deleted = T("Demographic deleted"),
            msg_list_empty = T("No Demographics currently defined"),
            )

        # Foreign Key Template
        represent = S3Represent(lookup=tablename)
        demographic_id = FieldTemplate("demographic_id", "reference %s" % tablename,
                                       label = T("Demographic"),
                                       represent = represent,
                                       requires = IS_EMPTY_OR(
                                                        IS_ONE_OF(db, "%s.id" % tablename,
                                                                  represent,
                                                                  filterby = "obsolete",
                                                                  filter_opts = (False,),
                                                                  )),
                                       sortby = "name",
                                       )

        # ---------------------------------------------------------------------
        # Testing Site Daily Summary Report
        # - for spatial-temporal analysis of testing activity and results
        #
        subtotals = settings.get_disease_testing_report_by_demographic()
        tablename = "disease_testing_report"
        define_table(tablename,
                     self.disease_disease_id(
                         ondelete = "CASCADE",
                         ),
                     self.super_link("site_id", "org_site",
                                     empty = False,
                                     instance_types = ("org_facility",
                                                       "hms_hospital",
                                                       ),
                                     label = T("Test Station"),
                                     represent = self.org_SiteRepresent(show_link = False,
                                                                        show_type = False,
                                                                        ),
                                     readable = True,
                                     writable = True,
                                     #ondelete = "CASCADE", # default
                                     ),
                     DateField(default="now",
                               past = 1,
                               future = 0,
                               ),
                     Field("tests_total", "integer",
                           label = T("Total Number of Tests"),
                           requires = IS_INT_IN_RANGE(0),
                           writable = not subtotals,
                           ),
                     Field("tests_positive", "integer",
                           label = T("Number of Positive Test Results"),
                           requires = IS_INT_IN_RANGE(0),
                           writable = not subtotals,
                           ),
                     CommentsField(),
                     )

        # Components
        self.add_components(tablename,
                            disease_testing_demographic = "report_id",
                            )

        # CRUD Form
        if subtotals:
            crud_fields = ["disease_id",
                           "site_id",
                           "date",
                           "tests_total",
                           "tests_positive",
                           InlineComponent("testing_demographic",
                                           label = T("Details"),
                                           fields = ["demographic_id",
                                                     "tests_total",
                                                     "tests_positive",
                                                     ],
                                           ),
                           "comments",
                           ]
        else:
            crud_fields = ["disease_id",
                           "site_id",
                           "date",
                           "tests_total",
                           "tests_positive",
                           "comments",
                           ]
        crud_form = CustomForm(*crud_fields)

        # Filter Widgets
        filter_widgets = [TextFilter(["site_id$name", "comments"],
                                     label = T("Search"),
                                     ),
                          DateFilter("date",
                                     ),
                          ]

        # List fields
        list_fields = ["date",
                       "site_id",
                       "disease_id",
                       "tests_total",
                       "tests_positive",
                       "comments",
                       ]

        # Report options
        facts = [(T("Number of Tests"), "sum(tests_total)"),
                 (T("Number of Positive Test Results"), "sum(tests_positive)"),
                 (T("Number of Reports"), "count(id)"),
                 ]
        axes = ["site_id",
                "site_id$location_id$L2",
                "site_id$location_id$L3",
                "disease_id",
                ]
        report_options = {
            "rows": axes,
            "cols": axes,
            "fact": facts,
            "defaults": {"rows": axes[1],
                         "cols": None,
                         "fact": facts[0],
                         "totals": True,
                         },
            }

        timeplot_options = {
            "facts": facts,
            "timestamp": ((T("per interval"), "date,date"),
                          (T("cumulative"), "date"),
                          ),
            "defaults": {"fact": facts[:2],
                         "timestamp": "date,date",
                         "time": "<-0 months||days",
                         },
            }

        # Table Configuration
        configure(tablename,
                  crud_form = crud_form,
                  list_fields = list_fields,
                  filter_widgets = filter_widgets,
                  onvalidation = self.testing_report_onvalidation,
                  orderby = "%s.date desc" % tablename,
                  report_options = report_options,
                  timeplot_options = timeplot_options,
                  )

        # CRUD Strings
        crud_strings[tablename] = Storage(
            label_create = T("Create Daily Report"),
            title_display = T("Daily Report"),
            title_list = T("Daily Reports"),
            title_update = T("Edit Daily Report"),
            label_list_button = T("List Daily Reports"),
            label_delete_button = T("Delete Daily Report"),
            msg_record_created = T("Daily Report created"),
            msg_record_modified = T("Daily Report updated"),
            msg_record_deleted = T("Daily Report deleted"),
            msg_list_empty = T("No Daily Reports currently registered"),
            )

        # ---------------------------------------------------------------------
        # Testing activity data per demographic
        # - component of testing reports
        #
        # TODO better represent (site+date)
        report_represent = S3Represent(lookup = "disease_testing_report",
                                       fields = ["date"],
                                       )
        tablename = "disease_testing_demographic"
        define_table(tablename,
                     Field("report_id", "reference disease_testing_report",
                           label = T("Report"),
                           represent = report_represent,
                           requires = IS_ONE_OF(db, "disease_testing_report.id",
                                                report_represent,
                                                ),
                           ),
                     demographic_id(
                         empty = False,
                         label = T("Subject Group##med"),
                         ondelete = "CASCADE",
                         ),
                     Field("tests_total", "integer",
                           label = T("Total Number of Tests"),
                           requires = IS_INT_IN_RANGE(0),
                           ),
                     Field("tests_positive", "integer",
                           label = T("Number of Positive Test Results"),
                           requires = IS_INT_IN_RANGE(0),
                           ),
                     CommentsField(),
                     )

        # List fields
        list_fields = ["report_id$site_id",
                       "report_id$date",
                       "demographic_id",
                       "tests_total",
                       "tests_positive",
                       "report_id$comments",
                       ]

        # Filter Widgets
        filter_widgets = [TextFilter(["report_id$site_id$name",
                                      "report_id$comments",
                                      ],
                                     label = T("Search"),
                                     ),
                          DateFilter("report_id$date",
                                     ),
                          ]

        # Report options
        facts = ((T("Number of Tests"), "sum(tests_total)"),
                 (T("Number of Positive Test Results"), "sum(tests_positive)"),
                 (T("Number of Reports"), "count(report_id)"),
                 )
        axes = ["report_id$site_id",
                "report_id$site_id$location_id$L2",
                "report_id$site_id$location_id$L3",
                "demographic_id",
                "report_id$disease_id",
                ]
        report_options = {
            "rows": axes,
            "cols": axes,
            "fact": facts,
            "defaults": {"rows": axes[1],
                         "cols": None,
                         "fact": facts[0],
                         "totals": True,
                         },
            }

        timeplot_options = {
            "facts": facts,
            "timestamp": ((T("per interval"), "report_id$date,report_id$date"),
                          (T("cumulative"), "report_id$date"),
                          ),
            "defaults": {"fact": list(facts[:2]),
                         "timestamp": "report_id$date,report_id$date",
                         "time": "<-0 months||days",
                         },
            }

        configure(tablename,
                  filter_widgets = filter_widgets,
                  list_fields = list_fields,
                  onvalidation = self.testing_demographic_onvalidation,
                  onaccept = self.testing_demographic_onaccept,
                  ondelete = self.testing_demographic_ondelete,
                  report_options = report_options,
                  timeplot_options = timeplot_options,
                  )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return {"disease_demographic_id": demographic_id,
                }

    # -------------------------------------------------------------------------
    def defaults(self):
        """ Safe defaults for names in case the module is disabled """

        dummy = FieldTemplate.dummy

        return {"disease_demographic_id": dummy("demographic_id"),
                }

    # -------------------------------------------------------------------------
    @staticmethod
    def testing_report_onvalidation(form):
        """
            Validate testing report:
            - prevent duplicate reports for the same site+date
            - check numbers for plausibility
        """

        form_vars = form.vars
        if "id" in form_vars:
            record_id = form_vars.id
        elif hasattr(form, "record_id"):
            record_id = form.record_id
        else:
            record_id = None

        # Extract disease_id, site_id, date
        form_data = lambda fn: form_vars[fn] if fn in form_vars else False
        context = {"disease_id": form_data("disease"),
                   "site_id": form_data("site_id"),
                   "date": form_data("date")
                   }

        T = current.T

        db = current.db
        s3db = current.s3db

        table = s3db.disease_testing_report
        if record_id:
            # Get missing context details from existing record
            missing = [table[fn] for fn in context if context[fn] is False]
            row = db(table.id == record_id).select(*missing,
                                                   limitby = (0, 1),
                                                   ).first()
            if row:
                for fn, v in context.items():
                    if v is False:
                        context[fn] = row[fn]
        else:
            # Get missing context details from defaults
            for fn, v in context.items():
                if v is False:
                    context[fn] = table[fn].default

        # Check for duplicate report
        query = None
        for fn, v in context.items():
            if v:
                q = (table[fn] == v)
                query = query & q if query else q
        if query:
            if record_id:
                query &= (table.id != record_id)
            duplicate = db(query).select(table.id, limitby=(0, 1)).first()
            if duplicate:
                form.errors["date"] = T("Report for this date exists - please update the existing report instead")

        # Validate numbers
        total = form_vars.get("tests_total")
        positive = form_vars.get("tests_positive")
        if total is not None and positive is not None:
            if positive > total:
                form.errors["tests_positive"] = T("Number of positive results cannot be greater than number of tests")

    # -------------------------------------------------------------------------
    @staticmethod
    def testing_demographic_onvalidation(form):
        """
            Onvalidation of testing_demographic:
            - check numbers for plausibility
        """

        T = current.T

        form_vars = form.vars

        # Validate numbers
        total = form_vars.get("tests_total")
        positive = form_vars.get("tests_positive")
        if total is not None and positive is not None:
            if positive > total:
                form.errors["tests_positive"] = T("Number of positive results cannot be greater than number of tests")

    # -------------------------------------------------------------------------
    @staticmethod
    def update_report_from_demographics(report_id):

        db = current.db
        s3db = current.s3db

        # Get totals for all demographics under this report
        table = s3db.disease_testing_demographic
        query = (table.report_id == report_id) & \
                (table.deleted == False)
        tests_total = table.tests_total.sum()
        tests_positive = table.tests_positive.sum()
        row = db(query).select(tests_total, tests_positive).first()

        # Update the report
        rtable = s3db.disease_testing_report
        query = (rtable.id == report_id) & \
                (rtable.deleted == False)
        db(query).update(tests_total = row[tests_total],
                         tests_positive = row[tests_positive],
                         )

    # -------------------------------------------------------------------------
    @classmethod
    def testing_demographic_onaccept(cls, form):
        """
            Onaccept of disease_testing_demographic:
            - update the totals in the corresponding report
        """

        # Get record ID
        form_vars = form.vars
        if "id" in form_vars:
            record_id = form_vars.id
        elif hasattr(form, "record_id"):
            record_id = form.record_id
        else:
            return

        table = current.s3db.disease_testing_demographic

        report_id = form_vars.get("report_id")
        if not report_id:
            record = current.db(table.id == record_id).select(table.report_id,
                                                              limitby = (0, 1),
                                                              ).first()
            if record:
                report_id = record.report_id

        if report_id:
            cls.update_report_from_demographics(report_id)

    # -------------------------------------------------------------------------
    @classmethod
    def testing_demographic_ondelete(cls, row):
        """
            Ondelete of disease_testing_demographic:
            - update the totals in the corresponding report
        """

        report_id = row.report_id

        if report_id:
            cls.update_report_from_demographics(report_id)

# =============================================================================
class DiseaseCertificateModel(DataModel):
    """
        Model to manage disease-related health certificates
    """

    names = ("disease_hcert_data",
             )

    def model(self):

        T = current.T

        #db = current.db
        #s3 = current.response.s3

        # ---------------------------------------------------------------------
        # Health Certificate Data
        #
        hcert_types = {"TEST": T("Test Certificate"),
                       "VACC": T("Vaccination Certificate"),
                       "RECO": T("Recovery Certificate"),
                       }
        hcert_status = {"PENDING": T("Pending"),
                        "ISSUED": T("Issued"),
                        "EXPIRED": T("Expired"),
                        "INVALID": T("Invalid"),
                        }
        tablename = "disease_hcert_data"
        self.define_table(tablename,
                          self.disease_disease_id(),
                          Field("type",
                                represent = represent_option(hcert_types),
                                requires = IS_IN_SET(hcert_types),
                                ),
                          Field("instance_id",
                                ),
                          Field("issuer_id",
                                ),
                          Field("payload", "json",
                                ),
                          Field("vhash", "text",
                                ),
                          Field("status",
                                represent = represent_option(hcert_status),
                                requires = IS_IN_SET(hcert_status),
                                ),
                          Field("errors", "text",
                                ),
                          # Date after which a certificate can no longer be issued
                          DateTimeField("valid_until",
                                        label = T("Valid until"),
                                        ),
                          # Date when the certificate was issued
                          DateTimeField("certified_on",
                                        label = T("Certified on"),
                                        ),
                          )

        self.configure(tablename,
                       insertable = False,
                       editable = False,
                       deletable = False,
                       )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

# =============================================================================
class DiseaseCaseTrackingModel(DataModel):

    names = ("disease_case",
             "disease_case_id",
             "disease_case_monitoring",
             "disease_case_monitoring_symptom",
             "disease_case_diagnostics",
             )

    def model(self):

        # @todo: add treatment component?

        T = current.T
        db = current.db

        settings = current.deployment_settings
        crud_strings = current.response.s3.crud_strings

        define_table = self.define_table
        configure = self.configure
        add_components = self.add_components

        person_id = self.pr_person_id

        # =====================================================================
        # Diagnosis Status
        #
        diagnosis_status = {"UNKNOWN": T("Unknown"),
                            "RISK": T("At Risk"),
                            "PROBABLE": T("Probable"),
                            "CONFIRMED-POS": T("Confirmed Positive"),
                            "CONFIRMED-NEG": T("Confirmed Negative"),
                            }
        diagnosis_status_represent = represent_option(diagnosis_status)

        # =====================================================================
        # Monitoring Levels
        #
        monitoring_levels = {"NONE": T("No Monitoring"),
                             # Clinical observation required:
                             "OBSERVATION": T("Observation"),
                             # Targeted diagnostics required:
                             "DIAGNOSTICS": T("Diagnostics"),
                             # Quarantine required:
                             "QUARANTINE": T("Quarantine"),
                             # Follow-up after recovery:
                             "FOLLOW-UP": T("Post-Recovery Follow-Up"),
                             }
        monitoring_level_represent = represent_option(monitoring_levels)
        # =====================================================================
        # Illness status
        #
        illness_status = {"UNKNOWN": T("Unknown, Not Checked"),
                          "ASYMPTOMATIC": T("Asymptomatic, Clinical Signs Negative"),
                          "SYMPTOMATIC": T("Symptomatic, Clinical Signs Positive"),
                          "SEVERE": T("Severely Ill, Clinical Signs Positive"),
                          "DECEASED": T("Deceased, Clinical Signs Positive"),
                          "RECOVERED": T("Recovered"),
                          }
        illness_status_represent = represent_option(illness_status)

        # =====================================================================
        # Case
        #
        use_case_number = settings.get_disease_case_number()
        use_case_id = settings.get_disease_case_id()
        use_treatment_notes = settings.get_disease_treatment()

        tablename = "disease_case"
        define_table(tablename,
                     Field("case_number", length=64,
                           requires = IS_EMPTY_OR([
                                IS_LENGTH(64),
                                IS_NOT_IN_DB(db, "disease_case.case_number"),
                                ]),
                           readable = use_case_number,
                           writable = use_case_number,
                           ),
                     person_id(empty = False,
                               ondelete = "CASCADE",
                               widget = PersonSelector(controller = "pr",
                                                       pe_label = use_case_id,
                                                       ),
                               ),
                     self.disease_disease_id(comment = None),
                     #DateField(), # date registered == created_on?
                     self.gis_location_id(),
                     # @todo: add site ID for registering site?

                     # Current illness status and symptom debut
                     Field("illness_status",
                           label = T("Current Illness Status"),
                           represent = illness_status_represent,
                           requires = IS_IN_SET(illness_status),
                           default = "UNKNOWN",
                           ),
                     DateField("symptom_debut",
                               label = T("Symptom Debut"),
                               ),
                     Field("hospitalized", "boolean",
                           default = False,
                           label = T("Hospitalized"),
                           represent = s3_yes_no_represent,
                           readable = not use_treatment_notes,
                           writable = not use_treatment_notes,
                           comment = DIV(_class="tooltip",
                                         _title="%s|%s" % (T("Hospitalized"),
                                                           T("Whether the person is currently in hospital"),
                                                           ),
                                         ),
                           ),
                     Field("intensive_care", "boolean",
                           default = False,
                           label = T("Intensive Care"),
                           represent = s3_yes_no_represent,
                           readable = not use_treatment_notes,
                           writable = not use_treatment_notes,
                           comment = DIV(_class="tooltip",
                                         _title="%s|%s" % (T("Intensive Care"),
                                                           T("Whether the person is currently in intensive care"),
                                                           ),
                                         ),
                           ),

                     # Current diagnosis status and date of last status update
                     Field("diagnosis_status",
                           label = T("Diagnosis Status"),
                           represent = diagnosis_status_represent,
                           requires = IS_IN_SET(diagnosis_status),
                           default = "UNKNOWN",
                           ),
                     DateField("diagnosis_date",
                               default = "now",
                               label = T("Diagnosis Date"),
                               ),

                     # Current monitoring level and end date
                     Field("monitoring_level",
                           label = T("Current Monitoring Level"),
                           represent = monitoring_level_represent,
                           requires = IS_IN_SET(monitoring_levels),
                           default = "NONE",
                           ),
                     DateField("monitoring_until",
                               label = T("Monitoring required until"),
                               ),
                     CommentsField(),
                     )

        # Foreign Key Template
        represent = disease_CaseRepresent()
        case_id = FieldTemplate("case_id", "reference %s" % tablename,
                                label = T("Case"),
                                represent = represent,
                                requires = IS_EMPTY_OR(
                                                IS_ONE_OF(db, "disease_case.id",
                                                          represent,
                                                          )),
                                comment = PopupLink(f = "case",
                                                    tooltip = T("Add a new case"),
                                                    ),
                                )

        # Components
        add_components(tablename,
                       disease_case_monitoring = "case_id",
                       disease_case_treatment = "case_id",
                       disease_case_diagnostics = "case_id",
                       disease_tracing = "case_id",
                       disease_exposure = ({"name": "exposure",
                                            "joinby": "person_id",
                                            "pkey": "person_id",
                                            },
                                            {"name": "contact",
                                             "joinby": "case_id",
                                             },
                                            ),
                       )

        # List fields
        case_number = "case_number" if use_case_number else None
        list_fields = ["disease_id",
                       case_number,
                       "person_id$pe_label" if use_case_id else None,
                       "person_id",
                       "illness_status",
                       "symptom_debut",
                       "hospitalized",
                       "intensive_care",
                       "diagnosis_status",
                       "diagnosis_date",
                       "monitoring_level",
                       "monitoring_until",
                       ]

        # CRUD form
        crud_form = CustomForm("disease_id",
                               case_number,
                               "person_id",
                               "location_id",
                               "illness_status",
                               "symptom_debut",
                               "hospitalized",
                               "intensive_care",
                               "diagnosis_status",
                               "diagnosis_date",
                               "monitoring_level",
                               "monitoring_until",
                               "comments",
                               )



        # Reports
        report_fields = ["disease_id"]
        levels = current.gis.get_relevant_hierarchy_levels()
        for level in levels:
            report_fields.append("location_id$%s" % level)

        report_fields.extend(["illness_status",
                              "hospitalized",
                              "intensive_care",
                              "monitoring_level",
                              "diagnosis_status",
                              ])
        report_options = {"rows": report_fields,
                          "cols": report_fields,
                          "fact": [(T("Number of Cases"), "count(id)"),
                                   ],
                          "defaults": {"rows": "location_id$L1",
                                       "cols": "diagnosis_status",
                                       "fact": "count(id)",
                                       "totals": True,
                                       },
                          }

        # Filters
        filter_widgets = [TextFilter(["case_number",
                                      "person_id$first_name",
                                      "person_id$middle_name",
                                      "person_id$last_name",
                                     ],
                                     label = T("Search"),
                                     comment = T("Enter Case Number or Name"),
                                     ),
                          OptionsFilter("monitoring_level",
                                        options = monitoring_levels,
                                        ),
                          OptionsFilter("diagnosis_status",
                                        options = diagnosis_status,
                                        ),
                          LocationFilter("location_id",
                                         ),
                          ]

        configure(tablename,
                  create_onvalidation = self.case_create_onvalidation,
                  crud_form = crud_form,
                  deduplicate = self.case_duplicate,
                  delete_next = URL(f="case", args=["summary"]),
                  filter_widgets = filter_widgets,
                  list_fields = list_fields,
                  onaccept = self.case_onaccept,
                  report_options = report_options,
                  )

        # CRUD strings
        crud_strings[tablename] = Storage(
            label_create = T("Create Case"),
            title_display = T("Case Details"),
            title_list = T("Cases"),
            title_update = T("Edit Cases"),
            title_upload = T("Import Cases"),
            label_list_button = T("List Cases"),
            label_delete_button = T("Delete Case"),
            msg_record_created = T("Case added"),
            msg_record_modified = T("Case updated"),
            msg_record_deleted = T("Case deleted"),
            msg_list_empty = T("No Cases currently registered"))

        # =====================================================================
        # Monitoring
        #
        tablename = "disease_case_monitoring"
        define_table(tablename,
                     case_id(empty=False),
                     DateTimeField(default="now"),
                     Field("illness_status",
                           represent = illness_status_represent,
                           requires = IS_IN_SET(illness_status),
                           ),
                     CommentsField(),
                     )

        # Components
        add_components(tablename,
                       disease_symptom = {"link": "disease_case_monitoring_symptom",
                                          "joinby": "status_id",
                                          "key": "symptom_id",
                                          }
                       )

        # Custom CRUD form
        crud_fields = ["case_id",
                       "date",
                       "illness_status",
                       InlineLink("symptom",
                                  field = "symptom_id",
                                  label = T("Symptoms"),
                                  multiple = True,
                                  ),
                       "comments",
                       ]

        configure(tablename,
                  crud_form = CustomForm(*crud_fields),
                  list_fields = ["date",
                                 "illness_status",
                                 (T("Symptoms"), "symptom.name"),
                                 "comments",
                                 ],
                  onaccept = self.monitoring_onaccept,
                  )

        # CRUD strings
        crud_strings[tablename] = Storage(
            label_create = T("Add Monitoring Update"),
            title_display = T("Monitoring Update"),
            title_list = T("Monitoring Updates"),
            title_update = T("Edit Monitoring Update"),
            title_upload = T("Import Monitoring Updates"),
            label_list_button = T("List Monitoring Updates"),
            label_delete_button = T("Delete Monitoring Update"),
            msg_record_created = T("Monitoring Update added"),
            msg_record_modified = T("Monitoring Update updated"),
            msg_record_deleted = T("Monitoring Update deleted"),
            msg_list_empty = T("No Monitoring Information currently available"))

        # =====================================================================
        # Monitoring <=> Symptom
        #
        tablename = "disease_case_monitoring_symptom"
        define_table(tablename,
                     Field("status_id", "reference disease_case_monitoring",
                           requires = IS_ONE_OF(db, "disease_case_monitoring.id"),
                           ),
                     self.disease_symptom_id(),
                     )

        # =====================================================================
        # Case Treatment/Progress Notes
        #
        occasions = (("HOSPITALIZED", T("Hospitalized")),
                     ("ICUIN", T("Admitted to Intensive Care")),
                     ("ICUOUT", T("Discharged from Intensive Care")),
                     ("DISCHARGED", T("Discharged from Hospital")),
                     ("VACCINATED", T("Vaccinated")),
                     ("OTHER", T("Other")),
                     )
        occasion_represent = represent_option(dict(occasions))
        tablename = "disease_case_treatment"
        define_table(tablename,
                     case_id(empty=False),
                     DateTimeField(default="now"),
                     Field("occasion",
                           represent = occasion_represent,
                           requires = IS_IN_SET(occasions,
                                                sort = False,
                                                ),
                           ),
                     CommentsField(),
                     )

        # Table configuration
        configure(tablename,
                  onaccept = self.treatment_onaccept,
                  )

        # CRUD strings
        crud_strings[tablename] = Storage(
            label_create = T("Add Treatment Note"),
            title_display = T("Treatment Note"),
            title_list = T("Treatment Notes"),
            title_update = T("Edit Note"),
            label_list_button = T("List Treatment Notes"),
            label_delete_button = T("Delete Treatment Note"),
            msg_record_created = T("Treatment Note added"),
            msg_record_modified = T("Treatment Note updated"),
            msg_record_deleted = T("Treatment Note deleted"),
            msg_list_empty = T("No Treatment Notes currently registered"),
            )

        # =====================================================================
        # Diagnostics
        #
        probe_status = {"PENDING": T("Pending"),
                        "PROCESSED": T("Processed"),
                        "VALIDATED": T("Validated"),
                        "INVALID": T("Invalid"),
                        "LOST": T("Lost"),
                        }

        project_id = self.project_project_id
        project_represent = project_id().represent

        tablename = "disease_case_diagnostics"
        define_table(tablename,
                     case_id(empty=False),
                     # Alternative link to disease for anonymous reporting
                     self.disease_disease_id(
                            readable = False,
                            writable = False,
                            ),
                     # Optional link to project funding this test
                     self.project_project_id(
                            requires = IS_EMPTY_OR(
                                            IS_ONE_OF(db, "project_project.id",
                                                      project_represent,
                                                      )),
                            readable = False,
                            writable = False,
                            ),
                     # Optional link to test station
                     self.super_link("site_id", "org_site",
                                     instance_types = ("org_facility",
                                                       "hms_hospital",
                                                       ),
                                     label = T("Test Station"),
                                     ondelete = "SET NULL",
                                     represent = self.org_SiteRepresent(show_link = False,
                                                                        show_type = False,
                                                                        ),
                                     readable = False,
                                     writable = False,
                                     ),
                     # Optional link to demographic for disease monitoring
                     self.disease_demographic_id(
                            label = T("Subject Group##med"),
                            readable = False,
                            writable = False,
                            ),
                     # @todo: make a lookup table in DiseaseDataModel:
                     Field("probe_type"),
                     Field("probe_number", length=64, unique=True,
                           requires = IS_LENGTH(64),
                           ),
                     DateTimeField("probe_date",
                                   default = "now",
                                   label = T("Probe Date"),
                                   future = 0,
                                   ),
                     Field("probe_status",
                           represent = represent_option(probe_status),
                           requires = IS_IN_SET(probe_status),
                           default = "PENDING",
                           ),
                     Field("test_type",
                           label = T("Test Type"),
                           ),
                     # Alternative to test type:
                     # - activate in template is/as needed
                     self.disease_testing_device_id(
                            label = T("Testing Device used"),
                            ondelete = "RESTRICT",
                            readable = False,
                            writable = False,
                            ),
                     Field("result",
                           label = T("Result"),
                           ),
                     DateField("result_date",
                               label = T("Result Date"),
                               ),
                     Field("conclusion",
                           represent = diagnosis_status_represent,
                           requires = IS_EMPTY_OR(
                                        IS_IN_SET(diagnosis_status)),
                           ),
                     CommentsField(),
                     )

        # CRUD strings
        crud_strings[tablename] = Storage(
            label_create = T("Add Diagnostic Test"),
            title_display = T("Diagnostic Test Details"),
            title_list = T("Diagnostic Tests"),
            title_update = T("Edit Diagnostic Test Details"),
            title_upload = T("Import Diagnostic Test Data"),
            label_list_button = T("List Diagnostic Tests"),
            label_delete_button = T("Delete Diagnostic Test"),
            msg_record_created = T("Diagnostic Test added"),
            msg_record_modified = T("Diagnostic Test updated"),
            msg_record_deleted = T("Diagnostic Test deleted"),
            msg_list_empty = T("No Diagnostic Tests currently registered"))

        # =====================================================================

        # Pass names back to global scope (s3.*)
        return {"disease_case_id": case_id,
                }

    # -------------------------------------------------------------------------
    def defaults(self):
        """ Safe defaults for names in case the module is disabled """

        return {"disease_case_id": FieldTemplate.dummy("case_id"),
                }

    # -------------------------------------------------------------------------
    @staticmethod
    def get_case(person_id, disease_id):
        """
            Find the case record for a person for a disease

            Args:
                person_id: the person record ID
                disease_id: the disease record ID
        """

        ctable = current.s3db.disease_case
        query = (ctable.person_id == person_id) & \
                (ctable.disease_id == disease_id) & \
                (ctable.deleted != True)
        record = current.db(query).select(ctable.id,
                                          ctable.case_number,
                                          limitby = (0, 1)).first()
        return record

    # -------------------------------------------------------------------------
    @classmethod
    def case_create_onvalidation(cls, form):
        """
            Make sure that there's only one case per person and disease
        """

        formvars = form.vars
        try:
            case_id = formvars.id
            person_id = formvars.person_id
        except AttributeError:
            return

        if "disease_id" not in formvars:
            disease_id = current.s3db.disease_case.disease_id.default
        else:
            disease_id = formvars.disease_id

        record = cls.get_case(person_id, disease_id)
        if record and record.id != case_id:
            error = current.T("This case is already registered")
            link = A(record.case_number,
                     _href=URL(f="case", args=[record.id]))
            form.errors.person_id = XML("%s: %s" % (error, link))

    # -------------------------------------------------------------------------
    @staticmethod
    def case_duplicate(item):
        """
            Case import update detection

            Args:
                item: the import item
        """

        data = item.data
        case_number = data.get("case_number")
        person_id = data.get("person_id")

        table = item.table
        if case_number:
            query = (table.case_number == case_number) & \
                    (table.deleted != True)
        else:
            disease_id = data.get("disease_id")
            if person_id and disease_id:
                query = (table.disease_id == disease_id) & \
                        (table.person_id == person_id) & \
                        (table.deleted != True)
            else:
                return

        duplicate = current.db(query).select(table.id,
                                             table.person_id,
                                             limitby=(0, 1)).first()
        if duplicate:
            item.data.person_id = duplicate.person_id
            item.id = duplicate.id
            item.method = item.METHOD.UPDATE

    # -------------------------------------------------------------------------
    @staticmethod
    def case_onaccept(form):
        """
            Propagate status updates of the case to high-risk contacts
        """

        formvars = form.vars
        try:
            record_id = formvars.id
        except AttributeError:
            return

        disease_propagate_case_status(record_id)

    # -------------------------------------------------------------------------
    @staticmethod
    def treatment_onaccept(form):

        formvars = form.vars
        try:
            record_id = formvars.id
        except AttributeError:
            return

        db = current.db
        s3db = current.s3db

        ctable = s3db.disease_case
        ttable = s3db.disease_case_treatment

        # Get the case_id
        query = (ttable.id == record_id) & \
                (ttable.deleted == False)
        row = db(query).select(ttable.case_id,
                               ttable.date,
                               limitby = (0, 1),
                               ).first()
        if row:
            case_id = row.case_id

            hospitalized = False
            query = (ttable.case_id == case_id) & \
                    (ttable.occasion.belongs(("HOSPITALIZED", "ICUIN"))) & \
                    (ttable.deleted == False)
            admission = db(query).select(ttable.date,
                                         limitby = (0, 1),
                                         orderby = ~ttable.date,
                                         ).first()
            if admission:
                query = (ttable.case_id == case_id) & \
                        (ttable.occasion == "DISCHARGED") & \
                        (ttable.date > admission.date) & \
                        (ttable.deleted == False)
                row = db(query).select(ttable.id,
                                       limitby = (0, 1),
                                       orderby = ttable.date,
                                       ).first()
                if not row:
                    hospitalized = True

            intensive_care = False
            query = (ttable.case_id == case_id) & \
                    (ttable.occasion == "ICUIN") & \
                    (ttable.deleted == False)
            admission = db(query).select(ttable.date,
                                         limitby = (0, 1),
                                         orderby = ~ttable.date,
                                         ).first()
            if admission:
                query = (ttable.case_id == case_id) & \
                        (ttable.occasion.belongs(("ICUOUT", "DISCHARGED"))) & \
                        (ttable.date > admission.date) & \
                        (ttable.deleted == False)
                row = db(query).select(ttable.id,
                                       limitby = (0, 1),
                                       orderby = ttable.date,
                                       ).first()
                if not row:
                    intensive_care = True

            db(ctable.id == case_id).update(hospitalized = hospitalized,
                                            intensive_care = intensive_care,
                                            )

    # -------------------------------------------------------------------------
    @staticmethod
    def monitoring_onaccept(form):
        """
            Update the illness status of the case from last monitoring entry
        """

        formvars = form.vars
        try:
            record_id = formvars.id
        except AttributeError:
            return

        db = current.db
        s3db = current.s3db

        ctable = s3db.disease_case
        mtable = s3db.disease_case_monitoring

        # Get the case ID
        case_id = None
        if "case_id" not in formvars:
            query = (mtable.id == record_id)
            row = db(query).select(mtable.case_id, limitby=(0, 1)).first()
            if row:
                case_id = row.case_id
        else:
            case_id = formvars.case_id
        if not case_id:
            return

        query = (mtable.case_id == case_id) & \
                (mtable.illness_status != None)

        row = db(query).select(mtable.illness_status,
                               orderby = "disease_case_monitoring.date desc",
                               limitby = (0, 1)).first()
        if row:
            db(ctable.id == case_id).update(illness_status = row.illness_status)
            # Propagate case status to contacts
            disease_propagate_case_status(case_id)

# =============================================================================
class disease_CaseRepresent(S3Represent):

    def __init__(self):

        super().__init__(lookup = "disease_case")

    # -------------------------------------------------------------------------
    def lookup_rows(self, key, values, fields=None):
        """
            Custom rows lookup

            Args:
                key: the key Field
                values: the values
                fields: unused (retained for API compatibility)
        """

        s3db = current.s3db

        table = self.table
        ptable = s3db.pr_person
        dtable = s3db.disease_disease

        left = [ptable.on(ptable.id == table.person_id),
                dtable.on(dtable.id == table.disease_id)]
        if len(values) == 1:
            query = (key == values[0])
        else:
            query = key.belongs(values)
        rows = current.db(query).select(table.id,
                                        table.case_number,
                                        dtable.name,
                                        dtable.short_name,
                                        dtable.acronym,
                                        ptable.first_name,
                                        ptable.last_name,
                                        left = left)
        self.queries += 1
        return rows

    # -------------------------------------------------------------------------
    def represent_row(self, row):
        """
            Represent a row

            Args:
                row: the Row
        """

        try:
            case_number = row[self.tablename].case_number
        except AttributeError:
            return row.case_number

        disease_name = None
        try:
            disease = row["disease_disease"]
        except AttributeError:
            pass
        else:
            for field in ("acronym", "short_name", "name"):
                if field in disease:
                    disease_name = disease[field]
                    if disease_name:
                        break

        if disease_name and case_number:
            case = "%s [%s]" % (case_number, disease_name)
        elif disease_name:
            case = "[%s]" % disease_name
        else:
            case = case_number

        try:
            person = row["pr_person"]
        except AttributeError:
            return case

        full_name = s3_fullname(person)
        if case:
            return " ".join((case, full_name))
        else:
            return full_name

# =============================================================================
class DiseaseContactTracingModel(DataModel):

    names = ("disease_tracing",
             "disease_exposure",
             )

    def model(self):

        T = current.T
        db = current.db

        crud_strings = current.response.s3.crud_strings
        define_table = self.define_table

        case_id = self.disease_case_id

        # =====================================================================
        # Tracing Information: when/where did a case pose risk for exposure?
        #

        # Processing Status
        contact_tracing_status = {
            "OPEN": T("Open"),         # not all contacts identified yet
            "COMPLETE": T("Complete"), # all contacts identified, closed
        }

        tablename = "disease_tracing"
        define_table(tablename,
                     case_id(empty=False),
                     DateTimeField("start_date",
                                   label = T("From"),
                                   set_min = "#disease_tracing_end_date",
                                   ),
                     DateTimeField("end_date",
                                   label = T("To"),
                                   set_max = "#disease_tracing_start_date",
                                   ),
                     # @todo: add site_id?
                     self.gis_location_id(),
                     Field("circumstances", "text",
                           ),
                     Field("status",
                           default = "OPEN",
                           label = T("Tracing Status"),
                           requires = IS_IN_SET(contact_tracing_status, zero=None),
                           represent = represent_option(contact_tracing_status),
                           ),
                     CommentsField(),
                     )

        # @todo: implement specific S3Represent class
        represent = S3Represent(lookup=tablename, fields=["case_id"])
        tracing_id = FieldTemplate("tracing_id", "reference %s" % tablename,
                                   label = T("Tracing Record"),
                                   represent = represent,
                                   requires = IS_EMPTY_OR(
                                                    IS_ONE_OF(db, "disease_tracing.id",
                                                              represent,
                                                              )),
                                   sortby = "date",
                                   comment = PopupLink(f = "tracing",
                                                       tooltip = T("Add a new contact tracing information"),
                                                       ),
                                   )

        self.add_components(tablename,
                            disease_exposure = "tracing_id",
                            )

        # CRUD strings
        crud_strings[tablename] = Storage(
            label_create = T("Add Tracing Record"),
            title_display = T("Tracing Details"),
            title_list = T("Contact Tracings"),
            title_update = T("Edit Tracing Information"),
            title_upload = T("Import Tracing Information"),
            label_list_button = T("List Tracing Record"),
            label_delete_button = T("Delete Tracing Record"),
            msg_record_created = T("Tracing Record added"),
            msg_record_modified = T("Tracing Record updated"),
            msg_record_deleted = T("Tracing Record deleted"),
            msg_list_empty = T("No Contact Tracings currently registered"))

        # =====================================================================
        # Protection
        #
        protection_level = {"UNKNOWN": T("Unknown"),
                            "NONE": T("No Protection"),
                            "PARTIAL": T("Partial"),
                            "FULL": T("Full"),
                            }
        protection_level_represent = represent_option(protection_level)

        # =====================================================================
        # Exposure Type
        #
        exposure_type = {"UNKNOWN": T("Unknown"),
                         "DIRECT": T("Direct"),
                         "INDIRECT": T("Indirect"),
                         }
        exposure_type_represent = represent_option(exposure_type)

        # =====================================================================
        # Exposure Risk Level
        #
        exposure_risk = {"UNKNOWN": T("Unknown"),
                         "NONE": T("No known exposure"),
                         "LOW": T("Low risk exposure"),
                         "HIGH": T("High risk exposure"),
                         }
        exposure_risk_represent = represent_option(exposure_risk)

        # =====================================================================
        # Exposure: when and how was a person exposed to the disease?
        #
        use_case_id = current.deployment_settings.get_disease_case_id()

        tablename = "disease_exposure"
        define_table(tablename,
                     self.pr_person_id(empty = False,
                                       widget = PersonSelector(controller = "pr",
                                                               pe_label = use_case_id,
                                                               ),
                                       ),
                     DateTimeField(
                         comment = DIV(_class="tooltip",
                                       _title="%s|%s" % (T("Exposure Date/Time"),
                                                         T("Date and Time when the person has been exposed"),
                                                         ),
                                       ),
                                 ),
                     case_id(label = T("Case exposed to"),
                             comment = DIV(_class="tooltip",
                                           _title="%s|%s" % (T("Case exposed to"),
                                                             T("The case this person has been exposed to (if known)"),
                                                             ),
                                           ),
                             ),
                     # Component link:
                     tracing_id(),

                     Field("exposure_type",
                           default = "UNKNOWN",
                           represent = exposure_type_represent,
                           requires = IS_IN_SET(exposure_type, zero=None),
                           ),
                     Field("protection_level",
                           default = "UNKNOWN",
                           represent = protection_level_represent,
                           requires = IS_IN_SET(protection_level, zero=None),
                           ),
                     Field("exposure_risk",
                           default = "LOW",
                           represent = exposure_risk_represent,
                           requires = IS_IN_SET(exposure_risk, zero=None),
                           ),
                     Field("circumstances", "text"),
                     )

        # List fields
        list_fields = ["person_id",
                       "date",
                       "case_id",
                       "exposure_type",
                       "protection_level",
                       "exposure_risk",
                       ]

        self.configure(tablename,
                       list_fields = list_fields,
                       onaccept = self.exposure_onaccept,
                       )

        crud_strings[tablename] = Storage(
            label_create = T("Add Exposure Information"),
            title_display = T("Exposure Details"),
            title_list = T("Exposure Information"),
            title_update = T("Edit Exposure Information"),
            title_upload = T("Import Exposure Information"),
            label_list_button = T("List Exposures"),
            label_delete_button = T("Delete Exposure Information"),
            msg_record_created = T("Exposure Information added"),
            msg_record_modified = T("Exposure Information updated"),
            msg_record_deleted = T("Exposure Information deleted"),
            msg_list_empty = T("No Exposure Information currently registered"))

        # Pass names back to global scope (s3.*)
        return None

    # -------------------------------------------------------------------------
    @staticmethod
    def exposure_onaccept(form):
        """
            TODO docstring
        """

        formvars = form.vars
        try:
            record_id = formvars.id
        except AttributeError:
            return

        db = current.db
        s3db = current.s3db

        # We need case_id, person_id and exposure_risk from the current record
        if "case_id" not in formvars:
            etable = s3db.disease_exposure
            row = db(etable.id == record_id).select(etable.case_id,
                                                    limitby = (0, 1)
                                                    ).first()
            if not row:
                return
            case_id = row.case_id
        else:
            case_id = formvars.case_id

        disease_propagate_case_status(case_id)

# =============================================================================
def disease_propagate_case_status(case_id):
    """
        TODO docstring
    """

    db = current.db
    s3db = current.s3db

    risk_status = ("SYMPTOMATIC", "SEVERE", "DECEASED", "RECOVERED")

    # Get the case
    ctable = s3db.disease_case
    query = (ctable.id == case_id) & \
            (ctable.deleted != True)
    case = db(query).select(ctable.id,
                            ctable.created_on,
                            ctable.disease_id,
                            ctable.illness_status,
                            ctable.symptom_debut,
                            ctable.diagnosis_status,
                            ctable.diagnosis_date,
                            limitby = (0, 1)
                            ).first()
    if case is None:
        return
    disease_id = case.disease_id

    # Try to establish a symptom debut
    symptom_debut = case.symptom_debut
    if not symptom_debut:
        # Get all monitoring entries for this case
        mtable = s3db.disease_case_monitoring
        query = (mtable.case_id == case_id) & \
                (mtable.illness_status.belongs(risk_status)) & \
                (mtable.deleted != True)
        monitoring = db(query).select(mtable.date,
                                      orderby = "disease_case_monitoring.date desc",
                                      limitby = (0, 1)
                                      ).first()
        if monitoring:
            symptom_debut = monitoring.date
    if not symptom_debut and case.illness_status in risk_status:
        symptom_debut = case.created_on
    if not symptom_debut:
        # Case is not known to ever have shown any symptoms
        return

    if case.diagnosis_status == "CONFIRMED-NEG" and \
       case.diagnosis_date > symptom_debut:
        # Case has been declared CONFIRMED-NEG after symptom debut
        return

    # Establish risk period (=symptom debut minus trace period)
    dtable = s3db.disease_disease
    query = (dtable.id == disease_id) & \
            (dtable.deleted != True)
    disease = db(query).select(dtable.trace_period,
                               dtable.watch_period,
                               limitby = (0, 1)
                               ).first()
    if not disease:
        return
    trace_period = disease.trace_period
    if trace_period:
        risk_period_start = symptom_debut - datetime.timedelta(days = disease.trace_period)
    else:
        risk_period_start = symptom_debut

    # Get all high-risk exposures after risk_period_start
    etable = s3db.disease_exposure
    query = (etable.case_id == case_id) & \
            (etable.date >= risk_period_start) & \
            (etable.exposure_risk == "HIGH") & \
            (etable.deleted != True)
    exposures = db(query).select(etable.person_id)
    for exposure in exposures:
        disease_create_case(disease_id,
                            exposure.person_id,
                            monitoring_level = "OBSERVATION",
                            )

# =============================================================================
def disease_create_case(disease_id, person_id, monitoring_level=None):
    """
        TODO docstring
    """

    ctable = current.s3db.disease_case
    query = (ctable.person_id == person_id) & \
            (ctable.disease_id == disease_id) & \
            (ctable.deleted != True)

    case = current.db(query).select(ctable.id,
                                    ctable.monitoring_level,
                                    limitby = (0, 1)
                                    ).first()
    if case:
        case_id = case.id
        if monitoring_level is not None:
            disease_upgrade_monitoring(case_id,
                                       monitoring_level,
                                       case=case,
                                       )
    else:
        case_id = ctable.insert(disease_id = disease_id,
                                person_id = person_id,
                                monitoring_level = monitoring_level,
                                )
    return case_id

# =============================================================================
def disease_upgrade_monitoring(case_id, level, case=None):
    """
        TODO docstring
    """

    if level not in MONITORING_UPGRADE:
        return
    else:
        previous_levels = MONITORING_UPGRADE[level]

    if case is None or "monitoring_level" not in case:
        ctable = current.s3db.disease_case
        query = (ctable.id == case_id) & \
                (ctable.monitoring_level.belongs(previous_levels)) & \
                (ctable.deleted != True)

        case = current.db(query).select(ctable.id,
                                        limitby = (0, 1)
                                        ).first()
    elif case.monitoring_level not in previous_levels:
        return

    if case:
        case.update_record(monitoring_level = level)

# =============================================================================
class DiseaseStatsModel(DataModel):
    """
        Disease Statistics:
            Cases:
                Confirmed/Suspected/Probable
            Deaths
    """

    names = ("disease_statistic",
             "disease_stats_data",
             "disease_stats_aggregate",
             "disease_stats_rebuild_all_aggregates",
             "disease_stats_update_aggregates",
             "disease_stats_update_location_aggregates",
             )

    def model(self):

        T = current.T
        NONE = current.messages["NONE"]

        configure = self.configure
        crud_strings = current.response.s3.crud_strings
        define_table = self.define_table
        super_link = self.super_link

        location_id = self.gis_location_id

        stats_parameter_represent = S3Represent(lookup = "stats_parameter",
                                                translate = True)

        # ---------------------------------------------------------------------
        # Disease Statistic Parameter
        #
        tablename = "disease_statistic"
        define_table(tablename,
                     # Instance
                     super_link("parameter_id", "stats_parameter"),
                     Field("name",
                           label = T("Name"),
                           requires = IS_NOT_EMPTY(),
                           represent = lambda v: T(v) if v is not None \
                                                    else NONE,
                           ),
                     CommentsField("description",
                                   label = T("Description"),
                                   ),
                     )

        # CRUD Strings
        ADD_STATISTIC = T("Add Statistic")
        crud_strings[tablename] = Storage(
            label_create = ADD_STATISTIC,
            title_display = T("Statistic Details"),
            title_list = T("Statistics"),
            title_update = T("Edit Statistic"),
            #title_upload = T("Import Statistics"),
            label_list_button = T("List Statistics"),
            msg_record_created = T("Statistic added"),
            msg_record_modified = T("Statistic updated"),
            msg_record_deleted = T("Statistic deleted"),
            msg_list_empty = T("No statistics currently defined"))

        configure(tablename,
                  deduplicate = S3Duplicate(),
                  super_entity = "stats_parameter",
                  )

        # ---------------------------------------------------------------------
        # Disease Statistic Data
        #
        tablename = "disease_stats_data"
        define_table(tablename,
                     # Instance
                     super_link("data_id", "stats_data"),
                     # This is a component, so needs to be a super_link
                     # - can't override field name, ondelete or requires
                     super_link("parameter_id", "stats_parameter",
                                instance_types = ("disease_statistic",),
                                label = T("Statistic"),
                                represent = stats_parameter_represent,
                                readable = True,
                                writable = True,
                                empty = False,
                                comment = PopupLink(c = "disease",
                                                    f = "statistic",
                                                    vars = {"child": "parameter_id"},
                                                    title = ADD_STATISTIC,
                                                    ),
                                ),
                     location_id(
                         requires = IS_LOCATION(),
                         widget = S3LocationAutocompleteWidget(),
                     ),
                     Field("value", "double",
                           label = T("Value"),
                           represent = lambda v: \
                            IS_FLOAT_AMOUNT.represent(v, precision=2),
                           requires = IS_NOT_EMPTY(),
                           ),
                     DateField(empty = False),
                     #Field("end_date", "date",
                     #      # Just used for the year() VF
                     #      readable = False,
                     #      writable = False
                     #      ),
                     # Link to Source
                     self.stats_source_id(),
                     CommentsField(),
                     )

        # CRUD Strings
        crud_strings[tablename] = Storage(
            label_create = T("Add Disease Data"),
            title_display = T("Disease Data Details"),
            title_list = T("Disease Data"),
            title_update = T("Edit Disease Data"),
            title_upload = T("Import Disease Data"),
            label_list_button = T("List Disease Data"),
            msg_record_created = T("Disease Data added"),
            msg_record_modified = T("Disease Data updated"),
            msg_record_deleted = T("Disease Data deleted"),
            msg_list_empty = T("No disease data currently available"))

        levels = current.gis.get_relevant_hierarchy_levels()

        location_fields = ["location_id$%s" % level for level in levels]

        list_fields = ["parameter_id"]
        list_fields.extend(location_fields)
        list_fields.extend((("value",
                             "date",
                             "source_id",
                             )))

        filter_widgets = [OptionsFilter("parameter_id",
                                        label = T("Type"),
                                        multiple = False,
                                        # Not translateable
                                        #represent = "%(name)s",
                                        ),
                          OptionsFilter("location_id$level",
                                        label = T("Level"),
                                        multiple = False,
                                        # Not translateable
                                        #represent = "%(name)s",
                                        ),
                          LocationFilter("location_id",
                                         levels = levels,
                                         ),
                          ]

        report_options = Storage(rows = location_fields,
                                 cols = ["parameter_id"],
                                 fact = [(T("Value"), "sum(value)"),
                                         ],
                                 defaults = Storage(rows = location_fields[0], # => L0 for multi-country, L1 for single country
                                                    cols = "parameter_id",
                                                    fact = "sum(value)",
                                                    totals = True,
                                                    chart = "breakdown:rows",
                                                    table = "collapse",
                                                    )
                                 )

        configure(tablename,
                  deduplicate = S3Duplicate(primary = ("parameter_id",
                                                       "location_id",
                                                       "date",
                                                       ),
                                            ),
                  filter_widgets = filter_widgets,
                  list_fields = list_fields,
                  report_options = report_options,
                  # @ToDo: Wrapper function to call this for the record linked
                  # to the relevant place depending on whether approval is
                  # required or not. Disable when auth.override is True.
                  #onaccept = self.disease_stats_update_aggregates,
                  #onapprove = self.disease_stats_update_aggregates,
                  # @ToDo: deployment_setting
                  #requires_approval = True,
                  super_entity = "stats_data",
                  timeplot_options = {"defaults": {"event_start": "date",
                                                   "event_end": "date",
                                                   "fact": "cumulate(value)",
                                                   },
                                      },
                  )

        #----------------------------------------------------------------------
        # Disease Aggregated data
        #

        # The data can be aggregated against:
        # location, all the aggregated values across a number of locations
        #           thus for an L2 it will aggregate all the L3 values
        # time, sum of all the disease_stats_data values up to this time.
        #           allowing us to report on cumulative values

        aggregate_types = {1 : T("Time"),
                           2 : T("Location"),
                           }

        tablename = "disease_stats_aggregate"
        define_table(tablename,
                     # This is a component, so needs to be a super_link
                     # - can't override field name, ondelete or requires
                     super_link("parameter_id", "stats_parameter",
                                empty = False,
                                instance_types = ("disease_statistic",),
                                label = T("Statistic"),
                                represent = S3Represent(lookup="stats_parameter"),
                                readable = True,
                                writable = True,
                                ),
                     location_id(
                        requires = IS_LOCATION(),
                        widget = S3LocationAutocompleteWidget(),
                     ),
                     Field("agg_type", "integer",
                           default = 1,
                           label = T("Aggregation Type"),
                           represent = lambda opt: \
                            aggregate_types.get(opt,
                                                current.messages.UNKNOWN_OPT),
                           requires = IS_IN_SET(aggregate_types),
                           ),
                     DateField("date",
                               label = T("Start Date"),
                               ),
                     Field("sum", "double",
                           label = T("Sum"),
                           represent = lambda v: \
                            IS_FLOAT_AMOUNT.represent(v, precision=2),
                           ),
                     )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return {"disease_stats_rebuild_all_aggregates": self.disease_stats_rebuild_all_aggregates,
                "disease_stats_update_aggregates": self.disease_stats_update_aggregates,
                "disease_stats_update_location_aggregates": self.disease_stats_update_location_aggregates,
                }

    # -------------------------------------------------------------------------
    @staticmethod
    def disease_stats_rebuild_all_aggregates():
        """
            This will delete all the disease_stats_aggregate records and
            then rebuild them by triggering off a request for each
            disease_stats_data record.

            This function is normally only run during prepop or postpop so we
            don't need to worry about the aggregate data being unavailable for
            any length of time
        """

        # Check to see whether an existing task is running and if it is then kill it
        db = current.db
        ttable = db.scheduler_task
        rtable = db.scheduler_run
        wtable = db.scheduler_worker
        query = (ttable.task_name == "disease_stats_update_aggregates") & \
                (rtable.task_id == ttable.id) & \
                (rtable.status == "RUNNING")
        rows = db(query).select(rtable.id,
                                rtable.task_id,
                                rtable.worker_name)
        now = current.request.utcnow
        for row in rows:
            db(wtable.worker_name == row.worker_name).update(status="KILL")
            db(rtable.id == row.id).update(stop_time=now,
                                           status="STOPPED")
            db(ttable.id == row.task_id).update(stop_time=now,
                                                status="STOPPED")

        # Delete the existing aggregates
        current.s3db.disease_stats_aggregate.truncate()

        # Read all the disease_stats_data records
        dtable = db.disease_stats_data
        query = (dtable.deleted != True)
        # @ToDo: deployment_setting to make this just the approved records
        #query &= (dtable.approved_by != None)
        records = db(query).select(dtable.parameter_id,
                                   dtable.date,
                                   dtable.value,
                                   dtable.location_id,
                                   )

        # Fire off a rebuild task
        current.s3task.run_async("disease_stats_update_aggregates",
                                 vars = {"records": records.json(),
                                         "all": True,
                                         },
                                 timeout = 21600 # 6 hours
                                 )

    # -------------------------------------------------------------------------
    @staticmethod
    def disease_stats_update_aggregates(records=None, all=False):
        """
            This will calculate the disease_stats_aggregates for the specified
            records. Either all (when rebuild_all is invoked) or for the
            individual parameter(s) at the specified location(s) when run
            onaccept/onapprove.
            @ToDo: onapprove/onaccept wrapper function.

            This will get the raw data from disease_stats_data and generate
            a disease_stats_aggregate record for the given time period.

            The reason for doing this is so that all aggregated data can be
            obtained from a single table. So when displaying data for a
            particular location it will not be necessary to try the aggregate
            table, and if it's not there then try the data table. Rather just
            look at the aggregate table.

            Once this has run then a complete set of aggregate records should
            exists for this parameter_id and location for every time period from
            the first data item until the current time period.

            @ToDo: Add test cases to modules/unit_tests/s3db/disease.py
         """

        if not records:
            return

        # Test to see which date format we have based on how we were called
        if isinstance(records, str):
            from_json = True
            from dateutil.parser import parse
            records = json.loads(records)
        elif isinstance(records[0]["date"],
                        (datetime.date, datetime.datetime)):
            from_json = False
        else:
            from_json = True
            from dateutil.parser import parse

        db = current.db
        #s3db = current.s3db
        atable = db.disease_stats_aggregate

        if not all:
            # Read the database to get all the relevant records
            # @ToDo: Complete this
            #dtable = s3db.disease_stats_data
            return

        # For each location/parameter pair, create a time-aggregate summing all
        # the data so far

        now = current.request.now

        # Assemble raw data
        earliest_period = now.date()
        locations = {}
        parameters = []
        pappend = parameters.append
        for record in records:
            location_id = record["location_id"]
            if location_id not in locations:
                locations[location_id] = {}
            parameter_id = record["parameter_id"]
            if parameter_id not in parameters:
                pappend(parameter_id)
            if parameter_id not in locations[location_id]:
                locations[location_id][parameter_id] = {}
            if from_json:
                date = parse(record["date"]) # produces a datetime
                date = date.date()
            else:
                date = record["date"]
            if date < earliest_period:
                earliest_period = date
            locations[location_id][parameter_id][date] = record["value"]

        # Full range of dates
        # 1 per day from the start of the data to the present day
        from dateutil.rrule import rrule, DAILY
        dates = rrule(DAILY, dtstart=earliest_period, until=now)
        dates = [d.date() for d in dates]

        # Add the sums
        insert = atable.insert
        lfield = atable.location_id
        pfield = atable.parameter_id
        dfield = atable.date
        ifield = atable.id
        _q = (atable.agg_type == 1)
        for location_id in locations:
            location = locations[location_id]
            query = _q & (lfield == location_id)
            for parameter_id in location:
                parameter = location[parameter_id]
                q = query & (pfield == parameter_id)
                for d in dates:
                    values = []
                    vappend = values.append
                    for date in parameter:
                        if date <= d:
                            vappend(parameter[date])
                    values_sum = sum(values)
                    exists = db(q & (dfield == d)).select(ifield,
                                                          limitby=(0, 1))
                    if exists:
                        db(ifield == exists.first().id).update(sum = values_sum)
                    else:
                        insert(agg_type = 1, # Time
                               location_id = location_id,
                               parameter_id = parameter_id,
                               date = d,
                               sum = values_sum,
                               )

        # For each location/parameter pair, build a location-aggregate for all
        # ancestors, by level (immediate parents first).
        # Ensure that we don't duplicate builds
        # Do this for all dates between the changed date and the current date

        # Get all the ancestors
        # Read all the Paths
        # NB Currently we're assuming that all Paths have been built correctly
        gtable = db.gis_location
        ifield = gtable.id
        location_ids = set(locations.keys())
        paths = db(ifield.belongs(location_ids)).select(gtable.path)
        paths = [p.path.split("/") for p in paths]
        # Convert list of lists to flattened list & remove duplicates
        import itertools
        ancestors = tuple(itertools.chain.from_iterable(paths))
        # Remove locations which we already have data for
        ancestors = [a for a in ancestors if a not in location_ids]

        # Get all the children for each ancestor (immediate children not descendants)
        pfield = gtable.parent
        query = (gtable.deleted == False) & \
                (pfield.belongs(ancestors))
        all_children = db(query).select(ifield, pfield)

        # Read the levels
        query = (gtable.id.belongs(ancestors)) & \
                (gtable.level.belongs(("L4", "L3", "L2", "L1"))) # L0?
        rows = db(query).select(gtable.id,
                                gtable.level,
                                # Build the lowest level first
                                # FIXME this ordering makes no real sense when building async
                                #       with multiple workers; in that case, the entire child
                                #       cascade must happen synchronously inside each top-level
                                #       build
                                orderby = ~gtable.level,
                                )

        run_async = current.s3task.run_async
        from gluon.serializers import json as jsons

        dates = jsons(dates)
        for row in rows:
            location_id = row.id
            children = [c.id for c in all_children if c.parent == location_id]
            children = json.dumps(children)
            for parameter_id in parameters:
                run_async("disease_stats_update_location_aggregates",
                          args = [location_id, children, parameter_id, dates],
                          timeout = 1800 # 30m
                          )

    # -------------------------------------------------------------------------
    @staticmethod
    def disease_stats_update_location_aggregates(location_id,
                                                 children,
                                                 parameter_id,
                                                 dates,
                                                 ):
        """
            Calculates the disease_stats_aggregate for a specific parameter at a
            specific location over the range of dates.

            Args:
                location_id: location to aggregate at
                children: locations to aggregate from
                parameter_id: arameter to aggregate
                dates: dates to aggregate for (as JSON string)
        """

        db = current.db
        atable = current.s3db.disease_stats_aggregate
        ifield = atable.id
        lfield = atable.location_id
        pfield = atable.parameter_id
        dfield = atable.date

        children = json.loads(children)

        # Get the most recent disease_stats_aggregate record for all child locations
        # - doesn't matter whether this is a time or location aggregate
        query = (pfield == parameter_id) & \
                (atable.deleted != True) & \
                (lfield.belongs(children))
        rows = db(query).select(atable.sum,
                                dfield,
                                lfield,
                                orderby=(lfield, ~dfield),
                                # groupby avoids duplicate records for the same
                                # location, but is slightly slower than just
                                # skipping the duplicates in the loop below
                                #groupby=(lfield)
                                )

        if not rows:
            return

        # Lookup which records already exist
        query = (lfield == location_id) & \
                (pfield == parameter_id)
        existing = db(query).select(ifield,
                                    dfield,
                                    )
        exists = {}
        for e in existing:
            exists[e.date] = e.id

        from dateutil.parser import parse
        dates = json.loads(dates)
        insert = atable.insert

        for date in dates:
            # Collect the values, skip duplicate records for the
            # same location => use the most recent one, which is
            # the first row for each location as per the orderby
            # in the query above
            date = parse(date) # produces a datetime
            date = date.date()
            last_location = None
            values = []
            vappend = values.append
            for row in rows:
                if date < row.date:
                    # Skip
                    continue
                new_location_id = row.location_id
                if new_location_id != last_location:
                    last_location = new_location_id
                    vappend(row.sum)

            if values:
                # Aggregate the values
                values_sum = sum(values)
            else:
                values_sum = 0

            # Add or update the aggregated values in the database
            attr = {"agg_type": 2, # Location
                    "sum": values_sum,
                    }

            # Do we already have a record?
            if date in exists:
                db(ifield == exists[date]).update(**attr)
            else:
                # Insert new
                insert(parameter_id = parameter_id,
                       location_id = location_id,
                       date = date,
                       **attr
                       )

# =============================================================================
def disease_rheader(r, tabs=None):
    """
        Resource Header for Disease module
    """

    if r.representation != "html":
        return None

    tablename, record = s3_rheader_resource(r)
    if tablename != r.tablename:
        resource = current.s3db.resource(tablename, id=record.id)
    else:
        resource = r.resource

    rheader = None
    rheader_fields = []

    if record:

        T = current.T
        settings = current.deployment_settings
        #record_id = record.id

        if tablename == "disease_disease":

            tabs = ((T("Basic Details"), None),
                    (T("Symptoms"), "symptom"),
                    (T("Documents"), "document"),
                    )

            rheader_fields = (["name"],
                              ["code"],
                              )
            rheader = S3ResourceHeader(rheader_fields, tabs)(r)

        elif tablename == "disease_case":

            tabs = [(T("Basic Details"), None),
                    (T("Person Data"), "person/"),
                    (T("Exposure"), "exposure"),
                    (T("Monitoring"), "case_monitoring"),
                    # Treatment
                    (T("Diagnostics"), "case_diagnostics"),
                    (T("Contacts"), "contact"),
                    (T("Tracing"), "tracing"),
                    ]

            # Optional tabs
            if settings.get_disease_treatment():
                tabs.insert(4, (T("Treatment"), "case_treatment"))

            case = resource.select(["person_id$pe_label",
                                    "person_id$gender",
                                    "person_id$date_of_birth",
                                    ],
                                    represent = True,
                                    raw_data = True,
                                    ).rows

            if not case:
                # Target record exists, but doesn't match filters
                return None

            # Extract case data
            case = case[0]
            gender = lambda row: case["pr_person.gender"]
            date_of_birth = lambda row: case["pr_person.date_of_birth"]

            if settings.get_disease_case_id():
                case_id = (T("ID"), lambda row: case["pr_person.pe_label"])
            elif settings.get_disease_case_number():
                case_id = "case_number"
            else:
                case_id = None

            rheader_fields = ([case_id,
                               "illness_status",
                               ],
                              ["person_id",
                               "diagnosis_status",
                               ],
                              [(T("Gender"), gender),
                               "hospitalized",
                               ],
                              [(T("Date of Birth"), date_of_birth),
                               "intensive_care",
                               ],
                              )
            rheader = S3ResourceHeader(rheader_fields, tabs)(r,
                                                             table = resource.table,
                                                             record = record,
                                                             )

        elif tablename == "disease_tracing":

            tabs = ((T("Basic Details"), None),
                    (T("Contact Persons"), "exposure"),
                    )

            rheader_fields = (["case_id"],
                              )
            rheader = S3ResourceHeader(rheader_fields, tabs)(r)

        else:
            rheader = None

    return rheader

# END =========================================================================
