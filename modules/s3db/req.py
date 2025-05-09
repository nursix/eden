"""
    Request Model

    Copyright: 2009-2022 (c) Sahana Software Foundation

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

__all__ = ("RequestModel",
           "RequestApproverModel",
           "RequestItemModel",
           "RequestSkillModel",
           "RequestRecurringModel",
           "RequestNeedsModel",
           "RequestNeedsActivityModel",
           "RequestNeedsContactModel",
           "RequestNeedsDemographicsModel",
           "RequestNeedsItemsModel",
           "RequestNeedsSkillsModel",
           "RequestNeedsOrganisationModel",
           "RequestNeedsPersonModel",
           "RequestNeedsSectorModel",
           "RequestNeedsSiteModel",
           "RequestNeedsTagModel",
           "RequestOrderItemModel",
           "RequestProjectModel",
           "RequestTagModel",
           "RequestTaskModel",
           "RequestRequesterCategoryModel",
           "CommitModel",
           "CommitItemModel",
           "CommitPersonModel",
           "CommitSkillModel",
           #"req_CheckMethod",
           "req_add_from_template",
           "req_approvers",
           "req_create_form_mods",
           "req_hide_quantities",
           "req_inline_form",
           #"req_is_approver",
           "req_match",
           "req_ref_represent",
           "req_rheader",
           "req_send_commit",
           "req_tabs",
           "req_update_status",
           "req_RequesterRepresent",
           "req_ReqItemRepresent",
           )

from gluon import *
from gluon.sqlhtml import StringWidget
from gluon.storage import Storage
from ..core import *
from core.ui.layouts import PopupLink

from .pr import OU

DEFAULT = "DEFAULT"

REQ_STATUS_NONE     = 0
REQ_STATUS_PARTIAL  = 1
REQ_STATUS_COMPLETE = 2
REQ_STATUS_CANCEL   = 3

# =============================================================================
def req_priority_opts():
    T = current.T
    return {3: T("High"),
            2: T("Medium"),
            1: T("Low")
            }

#def req_priority_represent(priority):
#    """
#        Represent request priority by a (color-coded) GIF image
#        @ToDo: make CSS-only
#    """

#    src = URL(c = "static",
#              f = "img",
#              args = ["priority", "priority_%d.gif" % (priority or 4)],
#              )
#    return DIV(IMG(_src= src))

def req_priority():
    priority_opts = req_priority_opts()
    return FieldTemplate("priority", "integer",
                         default = 2,
                         label = current.T("Priority"),
                         #@ToDo: Colour code the priority text - red, orange, green
                         #represent = req_priority_represent,
                         represent = represent_option(priority_opts),
                         requires = IS_EMPTY_OR(IS_IN_SET(priority_opts)),
                         )

# =============================================================================
def req_status_opts():
    T = current.T
    return {REQ_STATUS_NONE:     SPAN(T("None"),
                                      _class = "req_status_none",
                                      ),
            REQ_STATUS_PARTIAL:  SPAN(T("Partial"),
                                      _class = "req_status_partial",
                                      ),
            REQ_STATUS_COMPLETE: SPAN(T("Complete"),
                                      _class = "req_status_complete",
                                      ),
            }

def req_status():
    status_opts = req_status_opts()
    return FieldTemplate("req_status", "integer",
                         label = current.T("Request Status"),
                         represent = represent_option(status_opts),
                         requires = IS_EMPTY_OR(
                                        IS_IN_SET(status_opts,
                                                  zero = None,
                                                  )
                                        ),
                         )

# =============================================================================
def req_timeframe():
    T = current.T
    timeframe_opts = {1: T("0-12 hours"),
                      2: T("12-24 hours"),
                      3: T("1-2 days"),
                      4: T("2-4 days"),
                      5: T("5-7 days"),
                      6: T(">1 week"),
                      }
    return Field("timeframe", "integer",
                 default = 3,
                 label = T("Timeframe"),
                 represent = represent_option(timeframe_opts),
                 requires = IS_EMPTY_OR(
                                IS_IN_SET(timeframe_opts, zero = None),
                                ),
                 )

# =============================================================================
class RequestModel(DataModel):
    """
        Model for Requests
    """

    names = ("req_req",
             "req_req_id",
             "req_req_ref",
             )

    def model(self):

        T = current.T
        db = current.db
        auth = current.auth
        s3 = current.response.s3
        settings = current.deployment_settings

        messages = current.messages
        NONE = messages["NONE"]
        UNKNOWN_OPT = messages.UNKNOWN_OPT
        AUTOCOMPLETE_HELP = messages.AUTOCOMPLETE_HELP

        add_components = self.add_components
        crud_strings = s3.crud_strings
        set_method = self.set_method
        super_link = self.super_link

        person_id = self.pr_person_id
        req_status_field = req_status()

        # ---------------------------------------------------------------------
        # Model Options
        #
        ask_security = settings.get_req_ask_security()
        ask_transport = settings.get_req_ask_transport()
        date_writable = settings.get_req_date_writable()
        multiple_req_items = settings.get_req_multiple_req_items()
        recurring = settings.get_req_recurring()
        req_status_writable = settings.get_req_status_writable()
        requester_label = settings.get_req_requester_label()
        transit_status =  settings.get_req_show_quantity_transit()
        use_commit = settings.get_req_use_commit()
        use_req_number = settings.get_req_use_req_number()
        use_workflow = settings.get_req_workflow()

        # Request Types
        req_types_deployed = settings.get_req_req_type()
        req_types = {}
        if settings.has_module("inv") and "Stock" in req_types_deployed:
            # Number hardcoded in controller & JS
            req_types[1] = settings.get_req_type_inv_label()
        #if settings.has_module("asset") and "Asset" in req_types_deployed:
        #    req_types[2] = T("Assets")
        if settings.has_module("hrm") and "People" in req_types_deployed:
            req_types[3] = settings.get_req_type_hrm_label()
        #if settings.has_module("cr") and "Shelter" in req_types_deployed:
        #    req_types[4] = T("Shelter")
        if "Other" in req_types_deployed:
            req_types[9] = T("Other")

        # Default Request Type
        if len(req_types) == 1:
            default_type = list(req_types.keys())[0]
        else:
            default_type = current.request.get_vars.get("type")
            if default_type:
                default_type = int(default_type)

        # Defaults for Requesting Site and Requester
        requester_is_author = settings.get_req_requester_is_author()
        if requester_is_author and auth.s3_logged_in() and auth.user:
            site_default = auth.user.site_id
            requester_default = auth.s3_logged_in_person()
        else:
            site_default = None
            requester_default = None

        # Dropdown or Autocomplete for Requesting Site?
        if settings.get_org_site_autocomplete():
            site_widget = S3SiteAutocompleteWidget()
            site_comment = PopupLink(c = "org",
                                     f = "facility",
                                     vars = {"child":"site_id"},
                                     title = T("Create Facility"),
                                     tooltip = AUTOCOMPLETE_HELP,
                                     )
        else:
            site_widget = None
            site_comment = PopupLink(c = "org",
                                     f = "facility",
                                     vars = {"child": "site_id"},
                                     title = T("Create Facility"),
                                     )

        # Workflow options
        workflow_opts = {1: T("Draft"),
                         2: T("Submitted for Approval"),
                         3: T("Approved"),
                         4: T("Completed"),
                         5: T("Cancelled"),
                         }
        if use_workflow:
            workflow_default = 1 # Draft
        else:
            # Don't make assumptions
            workflow_default = None

        # ---------------------------------------------------------------------
        # Request Reference
        #
        req_ref = FieldTemplate("req_ref", "string",
                                label = T("%(REQ)s Number") %
                                        {"REQ": settings.get_req_shortname()},
                                represent = req_ref_represent,
                                writable = False,
                                )

        # ---------------------------------------------------------------------
        # Requests
        #
        tablename = "req_req"
        self.define_table(tablename,
                          # Instance
                          super_link("doc_id", "doc_entity"),
                          Field("type", "integer",
                                default = default_type,
                                label = T("Request Type"),
                                represent = lambda opt: \
                                            req_types.get(opt, UNKNOWN_OPT),
                                requires = IS_IN_SET(req_types, zero=None),
                                readable = not default_type,
                                writable = not default_type,
                                ),
                          req_ref(represent = lambda v, row=None: \
                                              req_ref_represent(v, show_link=False),
                                  readable = use_req_number,
                                  writable = use_req_number,
                                  widget = lambda f, v: \
                                    StringWidget.widget(f, v, _placeholder = T("Leave blank to have this autogenerated"))
                                  ),
                          DateTimeField(default = "now",
                                        label = T("Date Requested"),
                                        past = 8760, # Hours, so 1 year
                                        future = 0,
                                        readable = date_writable,
                                        writable = date_writable,
                                        #represent = "date",
                                        #widget = "date",
                                        ),
                          req_priority()(),
                          # This is a component, so needs to be a super_link
                          # - can't override field name, ondelete or requires
                          super_link("site_id", "org_site",
                                     comment = site_comment,
                                     default = site_default,
                                     empty = False,
                                     filterby = "obsolete",
                                     filter_opts = (False,),
                                     instance_types = auth.org_site_types,
                                     label = T("Requested For Facility"),
                                     readable = True,
                                     represent = self.org_site_represent,
                                     updateable = True,
                                     widget = site_widget,
                                     writable = True,
                                     ),
                          #Field("location",
                          #      label = T("Neighborhood")),
                          # Donations: What will the Items be used for?; People: Task Details
                          CommentsField("purpose",
                                        comment = "",
                                        label = T("Purpose"),
                                        # Only-needed for summary mode (unused)
                                        #represent = self.req_purpose_represent,
                                        represent = lambda s: s if s else NONE,
                                        ),
                          Field("is_template", "boolean",
                                default = False,
                                label = T("Recurring Request?"),
                                represent = s3_yes_no_represent,
                                readable = recurring,
                                writable = recurring,
                                comment = DIV(_class="tooltip",
                                              _title="%s|%s" % (T("Recurring Request?"),
                                                                T("If this is a request template to be added repeatedly then the schedule can be set on the next page."))),
                                ),
                          DateTimeField("date_required",
                                        label = T("Date Needed By"),
                                        past = 1, # Allow time for people to fill out form
                                        future = 8760, # Hours, so 1 year
                                        #represent = "date",
                                        #widget = "date",
                                        ),
                          DateTimeField("date_required_until",
                                        label = T("Date Required Until"),
                                        past = 0,
                                        future = 8760, # Hours, so 1 year
                                        readable = False,
                                        writable = False
                                        ),
                          person_id("requester_id",
                                    default = requester_default,
                                    empty = settings.get_req_requester_optional(),
                                    label = requester_label,
                                    represent = req_RequesterRepresent(),
                                    #writable = False,
                                    comment = PopupLink(c = "pr",
                                                        f = "person",
                                                        vars = {"child": "requester_id",
                                                                "parent": "req",
                                                                },
                                                        title = crud_strings["pr_person"].label_create,
                                                        tooltip = AUTOCOMPLETE_HELP,
                                                        ),
                                    ),
                          person_id("assigned_to_id", # This field should be in req_commit, but that complicates the UI
                                    label = T("Assigned To"),
                                    readable = False,
                                    writable = False,
                                    ),
                          person_id("approved_by_id",
                                    label = T("Approved By"),
                                    readable = False,
                                    writable = False,
                                    ),
                          person_id("request_for_id",
                                    #default = auth.s3_logged_in_person(),
                                    label = T("Requested For"),
                                    readable = False,
                                    writable = False,
                                    ),
                          Field("transport_req", "boolean",
                                label = T("Transportation Required"),
                                represent = s3_yes_no_represent,
                                readable = ask_transport,
                                writable = ask_transport,
                                ),
                          Field("security_req", "boolean",
                                label = T("Security Required"),
                                represent = s3_yes_no_represent,
                                readable = ask_security,
                                writable = ask_security,
                                ),
                          DateTimeField("date_recv",
                                        label = T("Date Received"), # Could be T("Date Delivered") - make deployment_setting or just use Template
                                        past = 8760, # Hours, so 1 year
                                        future = 0,
                                        readable = False,
                                        writable = False,
                                        ),
                          person_id("recv_by_id",
                                    # @ToDo: Set this in Update forms? Dedicated 'Receive' button?
                                    # (Definitely not in Create forms)
                                    #default = auth.s3_logged_in_person(),
                                    label = T("Received By"),
                                    ),
                          # Workflow Status
                          Field("workflow_status", "integer",
                                label = T("Status"),
                                default = workflow_default,
                                requires = IS_IN_SET(workflow_opts),
                                represent = represent_option(workflow_opts),
                                readable = use_workflow,
                                writable = False,
                                ),
                          # Simple Status
                          # - currently just enabled in customise_req_fields() workflow
                          req_status_field(readable = False,
                                           writable = False,
                                           ),
                          # Detailed Status
                          req_status_field("commit_status",
                                           label = T("Commit Status"),
                                           represent = self.req_commit_status_represent,
                                           readable = use_commit,
                                           writable = req_status_writable and use_commit,
                                           ),
                          req_status_field("transit_status",
                                           label = T("Transit Status"),
                                           readable = transit_status,
                                           writable = req_status_writable and transit_status,
                                           ),
                          req_status_field("fulfil_status",
                                           label = T("Fulfil. Status"),
                                           writable = req_status_writable,
                                           ),
                          #req_status_field("filing_status",
                          #                 label = T("Filing Status"),
                          #                 comment = DIV(_class="tooltip",
                          #                               _title="%s|%s" % (T("Filing Status"),
                          #                                                 T("Have all the signed documents for this shipment been filed?"))),
                          #                 readable = settings.get_req_document_filing(),
                          #                 writable = False,
                          #                 ),
                          Field("closed", "boolean",
                                default = False,
                                label = T("Closed"),
                                readable = not use_workflow,
                                writable = not use_workflow,
                                comment = DIV(_class = "tooltip",
                                              _title = "%s|%s" % (T("Closed"),
                                                                  T("No more items may be added to this request"),
                                                                  )),
                                ),
                          Field("cancel", "boolean",
                                default = False,
                                label = T("Cancel"),
                                ),
                          Field.Method("details", req_req_details),
                          Field.Method("drivers", req_req_drivers),
                          CommentsField(comment = ""),
                          )

        # CRUD strings
        crud_strings[tablename] = Storage(
            label_create = T("Make Request"),
            title_display = T("Request Details"),
            title_list = T("Requests"),
            title_map=T("Map of Requests"),
            title_report = T("Requests Report"),
            title_update = T("Edit Request"),
            label_list_button = T("List Requests"),
            label_delete_button = T("Delete Request"),
            msg_record_created = T("Request Added"),
            msg_record_modified = T("Request Updated"),
            msg_record_deleted = T("Request Canceled"),
            msg_list_empty = T("No Requests"))

        # Which levels of Hierarchy are we using?
        levels = current.gis.get_relevant_hierarchy_levels()

        filter_widgets = [
            #TextFilter(["committer_id$first_name",
            #            "committer_id$middle_name",
            #            "committer_id$last_name",
            #            "site_id$name",
            #            "comments",
            #            "req_id$name",
            #            "organisation_id$name"
            #            ],
            #           label = T("Search"),
            #           comment = T("Search for a Request by Committer name, Request ID, Site or Organization."),
            #           ),
            OptionsFilter("fulfil_status",
                          # Better to default (easier to customise/consistency)
                          #label = T("Fulfill Status"),
                          cols = 3,
                          ),
            LocationFilter("site_id$location_id",
                           levels = levels,
                           hidden = True,
                           ),
            OptionsFilter("site_id",
                          # Better to default (easier to customise/consistency)
                          #label = T("Requested For Facility"),
                          hidden = True,
                          ),
            OptionsFilter("created_by",
                          label = T("Logged By"),
                          hidden = True,
                          ),
            DateFilter("date",
                       # Better to default (easier to customise/consistency)
                       #label = T("Date Requested"),
                       hide_time = True,
                       input_labels = {"ge": "From", "le": "To"},
                       comment = T("Search for requests made between these dates."),
                       hidden = True,
                       ),
            DateFilter("date_required",
                       # Better to default (easier to customise/consistency)
                       #label = T("Date Needed By"),
                       hide_time = True,
                       input_labels = {"ge": "From", "le": "To"},
                       comment = T("Search for requests required between these dates."),
                       hidden = True,
                       ),
            ]

        position = 1
        if transit_status:
            position += 1
            filter_widgets.insert(0,
                                  OptionsFilter("transit_status",
                                                # Better to default (easier to customise/consistency)
                                                #label = T("Transit Status"),
                                                options = req_status_opts,
                                                cols = 3,
                                                ))

        if not default_type:
            filter_widgets.insert(position,
                                  OptionsFilter("type",
                                                label = T("Type"),
                                                cols = len(req_types),
                                                ))
        if default_type == 1 or (not default_type and 1 in req_types):
            filter_widgets.insert(position + 2,
                                  OptionsFilter("req_item.item_id$item_category_id",
                                                label = T("Item Category"),
                                                hidden = True,
                                                ))
        if default_type == 3 or (not default_type and 3 in req_types):
            filter_widgets.insert(position + 2,
                                  OptionsFilter("req_skill.skill_id",
                                                # Better to default (easier to customise/consistency)
                                                #label = T("Skill"),
                                                hidden = True,
                                                ))
        if use_commit:
            filter_widgets.insert(position,
                                  OptionsFilter("commit_status",
                                                # Better to default (easier to customise/consistency)
                                                #label = T("Commit Status"),
                                                options = req_status_opts,
                                                cols = 3,
                                                hidden = True,
                                                ))

        report_fields = ["priority",
                         "site_id$organisation_id",
                         ]
        rappend = report_fields.append
        for level in levels:
            rappend("site_id$location_id$%s" % level)
        rappend("site_id")
        # @ToDo: id gets stripped in _select_field
        fact_fields = report_fields + [(T("Requests"), "id")]

        # Foreign Key Template
        represent = self.req_represent
        req_id = FieldTemplate("req_id", "reference %s" % tablename,
                               label = T("Request"),
                               ondelete = "CASCADE",
                               represent = represent,
                               requires = IS_EMPTY_OR(
                                            IS_ONE_OF(db, "req_req.id",
                                                      lambda req_id, row=None: \
                                                             represent(req_id, row, show_link=False),
                                                      orderby = "req_req.date",
                                                      sort = True,
                                                      )),
                               sortby = "date",
                               )

        list_fields = ["id",
                       "date",
                       "date_required",
                       "site_id",
                       "requester_id",
                       ]

        # @ToDo: Allow a single column to support different components based on type
        # - this is the 'Details' VF
        # @ToDo: Include Qty too (Computed VF in component?)
        # - this is done in the 'Details' VF
        #if default_type == 1 or (not default_type and 1 in req_types):
        #    list_fields.append((T("Requested Items"), "req_item.item_id"))
        #if default_type == 3 or (not default_type and 3 in req_types):
        #    list_fields.append((T("Requested Skills"), "req_skill.skill_id"))

        if use_req_number:
            list_fields.insert(1, "req_ref")
        list_fields.extend(("priority",
                            (T("Details"), "details"),
                            ))
        if 1 in req_types:
            list_fields.append((T("Drivers"), "drivers"))
        if use_commit:
            list_fields.append("commit_status")
        if transit_status:
            list_fields.append("transit_status")
        list_fields.append("fulfil_status")
        if use_commit:
            list_fields.append((T("Committed By"), "commit.site_id"))

        self.configure(tablename,
                       context = {"location": "site_id$location_id",
                                  "organisation": "site_id$organisation_id",
                                  "site": "site_id",
                                  },
                       deduplicate = S3Duplicate(primary = ("req_ref",)),
                       extra_fields = ("req_ref", "type"),
                       filter_widgets = filter_widgets,
                       onaccept = self.req_onaccept,
                       ondelete = self.req_req_ondelete,
                       # Why was this set? Should be consistent with other resources
                       # Can add this to be specific templates/views which need this if-required
                       #listadd = False,
                       list_fields = list_fields,
                       orderby = "req_req.date desc",
                       report_options = Storage(
                            rows = report_fields,
                            cols = report_fields,
                            fact = fact_fields,
                            methods = ["count", "list", "sum"],
                            defaults = Storage(
                                rows = "site_id$location_id$%s" % levels[0], # Highest-level of hierarchy
                                cols = "priority",
                                fact = "count(id)",
                                totals = True,
                                )
                            ),
                       super_entity = "doc_entity",
                       # Leave this to templates
                       # - reduce load on templates which don't need this
                       #update_realm = True,
                       realm_components = ("req_item",
                                           "req_skill",
                                           ),
                       )

        # Custom Methods
        set_method("req_req",
                   method = "check",
                   action = req_CheckMethod())

        set_method("req_req",
                   method = "commit_all",
                   action = self.req_commit_all)

        set_method("req_req",
                   method = "copy_all",
                   action = self.req_copy_all)

        set_method("req_req",
                   method = "submit",
                   action = self.req_submit)

        set_method("req_req",
                   method = "approve_req", # Don't clash with core approve method
                   action = self.req_approve)

        # Print Forms
        set_method("req_req",
                   method = "form",
                   action = self.req_form)

        # Components
        add_components(tablename,
                       # Tags
                       req_req_tag = {"alias": "tag",
                                      "joinby": "req_id",
                                      },
                       # Requested Items
                       req_req_item = {"joinby": "req_id",
                                       "multiple": multiple_req_items,
                                       },
                       # Requested Skills
                       req_req_skill = {"joinby": "req_id",
                                        "multiple": multiple_req_items,
                                        },
                       # Commitment
                       req_commit = "req_id",
                       # Item Categories
                       supply_item_category = {"link": "req_req_item_category",
                                               "joinby": "req_id",
                                               "key": "item_category_id",
                                               },
                       # Approvers
                       req_approver_req = {"name": "approver",
                                           "joinby": "req_id",
                                           },

                       # Projects
                       req_project_req = {"joinby": "req_id",
                                          "multiple": False,
                                          },
                       project_project = {"link": "req_project_req",
                                          "joinby": "req_id",
                                          "key": "project_id",
                                          "actuate": "hide",
                                          "multiple": False,
                                          },
                       **{# Scheduler Jobs (for recurring requests)
                          S3Task.TASK_TABLENAME: {"name": "job",
                                                  "joinby": "req_id",
                                                  "link": "req_job",
                                                  "key": "scheduler_task_id",
                                                  "actuate": "replace",
                                                  },
                         }
                      )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return {"req_req_id": req_id,
                "req_req_ref": req_ref,
                }

    # -------------------------------------------------------------------------
    def defaults(self):
        """
            Safe defaults for model-global names in case module is disabled
        """

        dummy = FieldTemplate.dummy

        return {"req_req_id": dummy("req_id"),
                "req_req_ref": dummy("req_ref", "string"),
                }

    # -------------------------------------------------------------------------
    @staticmethod
    def req_represent(req_id, row=None, show_link=True, pdf=False):
        """
            Represent a Request

            TODO document parameters
            TODO S3Represent
        """

        if row:
            table = current.db.req_req
        elif not req_id:
            return current.messages["NONE"]
        else:
            req_id = int(req_id)
            if req_id:
                db = current.db
                table = db.req_req
                row = db(table.id == req_id).select(table.date,
                                                    table.req_ref,
                                                    table.site_id,
                                                    limitby = (0, 1)
                                                    ).first()
        try:
            if row.req_ref:
                req = row.req_ref
            else:
                req = "%s - %s" % (table.site_id.represent(row.site_id,
                                                           show_link=False),
                                   table.date.represent(row.date))
        except (AttributeError, TypeError):
            return current.messages.UNKNOWN_OPT

        if show_link:
            if pdf:
                args = [req_id, "form"]
                _title = current.T("Open PDF")
            else:
                args = [req_id]
                _title = current.T("Go to Request")
            return A(req,
                     _href = URL(c="req", f="req",
                                 args=args,
                                 ),
                     _title = _title)
        else:
            return req

    # -------------------------------------------------------------------------
    @staticmethod
    def req_commit_status_represent(commit_status):
        """
            Represet the Commitment Status of the Request
        """

        if commit_status == REQ_STATUS_COMPLETE:
            # Include the Site Name of the Committer if we can
            # @ToDo: figure out how!
            return SPAN(current.T("Complete"),
                        _class = "req_status_complete",
                        )
        else:
            return req_status_opts().get(commit_status,
                                         current.messages.UNKNOWN_OPT)

    # -------------------------------------------------------------------------
    @staticmethod
    def req_copy_all(r, **attr):
        """
            Copy an existing Request (custom REST method)
                - creates a req with req_item records
        """

        db = current.db
        s3db = current.s3db
        table = s3db.req_req
        settings = current.deployment_settings
        now = current.request.now

        record = r.record
        req_id = record.id
        # Make a copy of the request record
        if settings.get_req_use_req_number():
            code = s3db.supply_get_shipping_code(settings.get_req_shortname(),
                                                 record.site_id,
                                                 table.req_ref,
                                                 )
        else:
            code = None
        if record.date_required and record.date_required < now:
            date_required = now + datetime.timedelta(days=14)
        else:
            date_required = record.date_required
        new_req_id = table.insert(type = record.type,
                                  req_ref = code,
                                  date = now,
                                  date_required = date_required,
                                  priority = record.priority,
                                  site_id = record.site_id,
                                  purpose = record.purpose,
                                  requester_id = record.requester_id,
                                  transport_req = record.transport_req,
                                  security_req = record.security_req,
                                  comments = record.comments,
                                  )
        # Make a copy of each child record
        if record.type == 1:
            # Items
            ritable = s3db.req_req_item
            items = db(ritable.req_id == req_id).select(ritable.id,
                                                        ritable.item_entity_id,
                                                        ritable.item_id,
                                                        ritable.item_pack_id,
                                                        ritable.quantity,
                                                        ritable.pack_value,
                                                        ritable.currency,
                                                        ritable.site_id,
                                                        ritable.comments,
                                                        )
            if items:
                insert = ritable.insert
                for item in items:
                    insert(req_id = new_req_id,
                           item_entity_id = item.item_entity_id,
                           item_id = item.item_id,
                           item_pack_id = item.item_pack_id,
                           quantity = item.quantity,
                           pack_value = item.pack_value,
                           currency = item.currency,
                           site_id = item.site_id,
                           comments = item.comments,
                           )
        elif record.type == 3:
            # People and skills
            rstable = s3db.req_req_skill
            skills = db(rstable.req_id == req_id).select(rstable.id,
                                                         rstable.skill_id,
                                                         rstable.quantity,
                                                         rstable.site_id,
                                                         rstable.comments,
                                                         )
            if skills:
                insert = rstable.insert
                for skill in skills:
                    insert(req_id = new_req_id,
                           skill_id = skill.skill_id,
                           quantity = skill.quantity,
                           site_id = skill.site_id,
                           comments = skill.comments,
                           )

        redirect(URL(f = "req",
                     args = [new_req_id, "update"],
                     ))

    # -------------------------------------------------------------------------
    @staticmethod
    def req_commit_all(r, **attr):
        """
            Custom Method to commit to a Request
                - creates a commit with commit_items for each req_item or
                  commit_skills for each req_skill
        """

        T = current.T
        db = current.db
        s3db = current.s3db
        table = s3db.req_commit

        record = r.record
        req_id = record.id

        # Check if there is an existing Commitment
        query = (table.req_id == req_id) & \
                (table.deleted == False)
        exists = db(query).select(table.id,
                                  limitby = (0, 1)
                                  ).first()
        if exists:
            # Browse existing commitments
            redirect(URL(f = "req",
                         args = [r.id, "commit"],
                         ))

        req_type = record.type

        # Create the commitment
        cid = table.insert(req_id = req_id,
                           type = req_type,
                           )

        if req_type == 1:
            # Items
            ritable = s3db.req_req_item
            items = db(ritable.req_id == req_id).select(ritable.id,
                                                        ritable.item_pack_id,
                                                        ritable.quantity,
                                                        ritable.comments,
                                                        )
            if items:
                citable = s3db.req_commit_item
                insert = citable.insert
                for item in items:
                    commit_item_id = item.id
                    quantity = item.quantity
                    insert(commit_id = cid,
                           req_item_id = commit_item_id,
                           item_pack_id = item.item_pack_id,
                           quantity = quantity,
                           comments = item.comments,
                           )
                    # Mark Item in the Request as Committed
                    db(ritable.id == commit_item_id).update(quantity_commit = quantity)
            # Mark Request as Committed
            db(s3db.req_req.id == req_id).update(commit_status = REQ_STATUS_COMPLETE)
            msg = T("You have committed to all items in this Request. Please check that all details are correct and update as-required.")

        elif req_type == 3:
            # People
            rstable = s3db.req_req_skill
            skills = db(rstable.req_id == req_id).select(rstable.id,
                                                         rstable.skill_id,
                                                         rstable.quantity,
                                                         rstable.comments,
                                                         )
            if skills:
                # @ToDo:
                #if current.deployment_settings.get_req_commit_people():
                #else:
                cstable = s3db.req_commit_skill
                insert = cstable.insert
                for skill in skills:
                    commit_skill_id = skill.id
                    quantity = skill.quantity
                    insert(commit_id = cid,
                           skill_id = skill.skill_id,
                           quantity = quantity,
                           comments = skill.comments,
                           )
                    # Mark Item in the Request as Committed
                    db(rstable.id == commit_skill_id).update(quantity_commit = quantity)
            # Mark Request as Committed
            db(s3db.req_req.id == req_id).update(commit_status = REQ_STATUS_COMPLETE)
            msg = T("You have committed for all people in this Request. Please check that all details are correct and update as-required.")

        else:
            # Other
            # Mark Request as Committed
            db(s3db.req_req.id == req_id).update(commit_status = REQ_STATUS_COMPLETE)
            msg = T("You have committed to this Request. Please check that all details are correct and update as-required.")

        if "send" in r.args:
            redirect(URL(f = "send_commit",
                         args = [cid],
                         ))

        elif "assign" in r.args:
            redirect(URL(f = "commit",
                         args = [cid, "assign"],
                         ))

        else:
            current.session.confirmation = msg
            redirect(URL(c="req", f="commit",
                         args = [cid],
                         ))

    # -------------------------------------------------------------------------
    @staticmethod
    def req_form(r, **attr):
        """
            Generate a PDF of a Request Form (custom REST method)
        """

        record = r.record

        if record.type == 1:
            pdf_componentname = "req_item"
            list_fields = ["item_id",
                           "item_pack_id",
                           "quantity",
                           "quantity_commit",
                           "quantity_transit",
                           "quantity_fulfil",
                           ]
        elif record.type == 3:
            pdf_componentname = "req_skill"
            list_fields = ["skill_id",
                           "quantity",
                           "quantity_commit",
                           "quantity_transit",
                           "quantity_fulfil",
                           ]
        else:
            # Not Supported - redirect to normal PDF
            redirect(URL(args = current.request.args[0],
                         extension = "pdf"))

        if current.deployment_settings.get_req_use_req_number():
            filename = record.req_ref
        else:
            filename = None

        from core import DataExporter
        exporter = DataExporter.pdf
        return exporter(r.resource,
                        request = r,
                        method = "list",
                        pdf_title = current.deployment_settings.get_req_form_name(),
                        pdf_filename = filename,
                        list_fields = list_fields,
                        pdf_hide_comments = True,
                        pdf_componentname = pdf_componentname,
                        pdf_header_padding = 12,
                        #pdf_footer = inv_recv_pdf_footer,
                        pdf_table_autogrow = "B",
                        pdf_orientation = "Landscape",
                        **attr
                        )

    # -------------------------------------------------------------------------
    @staticmethod
    def req_submit(r, **attr):
        """
            Submit a Request for Approval (custom REST method)
        """

        record = r.record
        req_id = r.id

        # Check we are the right place in the workflow
        if record.workflow_status != 1:
            current.session.error = current.T("Can only Submit Draft Requests")
            redirect(URL(args = req_id))

        s3db = current.s3db
        rtable = s3db.req_req

        # Check we have permission to update the Request
        if not current.auth.s3_has_permission("update", rtable, record_id=req_id):
            r.unauthorised()

        db = current.db

        # Lookup Approver(s)
        site_id = record.site_id
        stable = s3db.org_site
        site_entity = db(stable.site_id == site_id).select(stable.instance_type,
                                                           limitby = (0, 1)
                                                           ).first()
        itable = s3db.table(site_entity.instance_type)
        site = db(itable.site_id == site_id).select(itable.name, # Needed later for Message construction
                                                    itable.pe_id,
                                                    limitby = (0, 1)
                                                    ).first()
        pe_id = site.pe_id
        ancestors = s3db.pr_get_ancestors(pe_id)
        pe_ids = ancestors + [pe_id]
        atable = s3db.req_approver
        ptable = s3db.pr_person
        ltable = s3db.pr_person_user
        utable = db.auth_user
        query = (atable.pe_id.belongs(pe_ids)) & \
                (atable.person_id == ptable.id) & \
                (ptable.pe_id == ltable.pe_id) & \
                (ltable.user_id == utable.id)
        approvers = db(query).select(ptable.pe_id,
                                     utable.language,
                                     )
        if not approvers:
            current.session.error = current.T("No Request Approver defined")
            redirect(URL(args = req_id))

        # Send Localised Mail(s)
        T = current.T
        languages = {}
        for row in approvers:
            language = row["auth_user.language"]
            if language not in languages:
                languages[language] = []
            languages[language].append(row["pr_person.pe_id"])
        session_s3 = current.session.s3
        ui_language = session_s3.language
        url = "%s%s" % (current.deployment_settings.get_base_public_url(),
                        URL(c="req", f="req",
                            args = req_id,
                            ))
        req_ref = record.req_ref
        requester = record.requester_id
        date_required = record.date_required
        date_represent = S3DateTime.date_represent # We want Dates not datetime which table.date_required uses
        site_name = site.name
        send_email = current.msg.send_by_pe_id
        subject_T = T("Request submitted for Approval")
        message_T = T("A new Request, %(reference)s, has been submitted for Approval by %(person)s for delivery to %(site)s by %(date_required)s. Please review at: %(url)s")
        for language in languages:
            T.force(language)
            session_s3.language = language # for date_represent
            subject = "%s: %s" % (s3_str(subject_T), req_ref)
            message = s3_str(message_T) % {"date_required": date_represent(date_required),
                                           "reference": req_ref,
                                           "person": requester,
                                           "site": site_name,
                                           "url": url,
                                           }
            users = languages[language]
            for pe_id in users:
                send_email(pe_id,
                           subject = subject,
                           message = message,
                           )
        # Restore language for UI
        session_s3.language = ui_language
        T.force(ui_language)

        # Update the Status
        db(rtable.id == req_id).update(workflow_status = 2) # Submitted

        current.session.confirmation = T("Request submitted for Approval")
        redirect(URL(args = req_id))

    # -------------------------------------------------------------------------
    @staticmethod
    def req_approve(r, **attr):
        """
            Approve a Request (custom REST method)

            NB This is currently hardcoded to Items Requests not Person Requests
            NB This is currently hardcoded to RMS roles
        """

        record = r.record

        # Check we are the right place in the workflow
        if record.workflow_status != 2:
            current.session.error = current.T("Can only Approve Submitted Requests")
            redirect(URL(args = r.id))

        s3db = current.s3db
        rtable = s3db.req_req

        req_id = r.id

        approvers = req_approvers(record.site_id)
        person_id = current.auth.s3_logged_in_person()

        # Check we have permission to approve the Request
        if person_id not in approvers:
            r.unauthorised()

        db = current.db

        # Check if this person has already approved the Request
        artable = s3db.req_approver_req
        approved = db(artable.req_id == req_id).select(artable.person_id)
        approved = [row.person_id for row in approved]
        if person_id in approved:
            current.session.warning = current.T("You have already Approved this Request")
            redirect(URL(args = req_id))

        ritable = s3db.req_req_item
        query = (ritable.req_id == req_id) & \
                (ritable.deleted == False)
        request_items = db(query).select(ritable.id,
                                         ritable.site_id,
                                         )
        site_ids = [row.site_id for row in request_items]

        approver = approvers[person_id]

        if approver["matcher"]:
            # This person is responsible for Matching Items to Warehouses
            if None in site_ids:
                # Check for Purchases
                unmatched_items = [row.id for row in request_items if row.site_id == None]
                oitable = s3db.req_order_item
                orders = db(oitable.req_item_id.belongs(unmatched_items)).select(oitable.id)
                if len(unmatched_items) != len(orders):
                    current.session.warning = current.T("You need to Match Items in this Request")
                    redirect(URL(args = [req_id, "req_item"]))

        # Add record to show that we have approved request
        artable.insert(req_id = req_id,
                       person_id = person_id,
                       title = approver["title"],
                       )

        T = current.T
        session = current.session

        # Have all Approvers approved the Request?
        if len(approvers) == len(approved) + 1:
            # Update the Status
            db(rtable.id == req_id).update(workflow_status = 3, # Approved
                                           )
            # Notify the Warehouse Operator(s)
            session_s3 = session.s3
            ui_language = session_s3.language
            url = "%s%s" % (current.deployment_settings.get_base_public_url(),
                            URL(c="req", f="req",
                                args = [req_id, "req_item"],
                                ))
            req_ref = record.req_ref
            date_required = record.date_required
            date_represent = S3DateTime.date_represent # We want Dates not datetime which table.date_required uses
            send_email = current.msg.send_by_pe_id
            subject_T = T("Request Approved for Items from your Warehouse")
            message_T = T("A new Request, %(reference)s, has been Approved for shipment from %(site)s by %(date_required)s. Please review at: %(url)s")

            site_ids = set(site_ids)
            stable = s3db.org_site
            site_entities = db(stable.site_id.belongs(site_ids)).select(stable.site_id,
                                                                        stable.instance_type,
                                                                        )
            # Sort by Instance Type
            sites_by_type = {}
            for row in site_entities:
                instance_type = row.instance_type
                if instance_type not in sites_by_type:
                    sites_by_type[instance_type] = []
                sites_by_type[instance_type].append(row.site_id)

            # Lookup Names & PE IDs
            sites = {}
            for instance_type in sites_by_type:
                itable = s3db.table(instance_type)
                instances = db(itable.site_id.belongs(sites_by_type[instance_type])).select(itable.name,
                                                                                            itable.pe_id,
                                                                                            itable.site_id,
                                                                                            )
                for row in instances:
                    sites[row.site_id] = {"name": row.name,
                                          "pe_id": row.pe_id,
                                          }
            gtable = db.auth_group
            mtable = db.auth_membership
            utable = db.auth_user
            ltable = s3db.pr_person_user

            atable = s3db.pr_affiliation
            rtable = s3db.pr_role

            # Lookup realm for all wh_operator with default realm outside of loop
            # NB The role name is specific to RMS template currently, which is the only one to use this workflow
            # Incorporates a Bulk version of s3db.pr_realm()
            query = (gtable.uuid == "wh_operator") & \
                    (gtable.id == mtable.group_id) & \
                    (mtable.pe_id == None) & \
                    (mtable.deleted == False) & \
                    (mtable.user_id == utable.id) & \
                    (utable.id == ltable.user_id) & \
                    (atable.pe_id == ltable.pe_id) & \
                    (atable.deleted == False) & \
                    (atable.role_id == rtable.id) & \
                    (rtable.deleted == False) & \
                    (rtable.role_type == OU)
            wh_operators_default_realm = db(query).select(ltable.pe_id,
                                                          utable.language,
                                                          rtable.pe_id,
                                                          )

            for site_id in sites:

                site = sites[site_id]
                site_name = site["name"]
                pe_id = site["pe_id"]

                # Find the relevant wh_operator
                # NB The role name is specific to RMS template currently, which is the only one to use this workflow
                entities = s3db.pr_get_ancestors(pe_id)
                entities.append(pe_id)

                query = (gtable.uuid == "wh_operator") & \
                        (gtable.id == mtable.group_id) & \
                        (mtable.pe_id.belongs(entities)) & \
                        (mtable.deleted == False) & \
                        (mtable.user_id == utable.id) & \
                        (utable.id == ltable.user_id)
                operators = db(query).select(ltable.pe_id,
                                             utable.language,
                                             )
                operators = list(operators)
                for row in wh_operators_default_realm:
                    if row["pr_role.pe_id"] in entities:
                        operators.append(row)

                if not operators:
                    # Send to logs_manager instead
                    # NB We lookup the ones with default realm inside the loop as we don't expect to his this often
                    query = (gtable.uuid == "logs_manager") & \
                            (gtable.id == mtable.group_id) & \
                            ((mtable.pe_id.belongs(entities)) | \
                             (mtable.pe_id == None)) & \
                            (mtable.deleted == False) & \
                            (mtable.user_id == utable.id) & \
                            (utable.id == ltable.user_id)
                    users = db(query).select(ltable.pe_id,
                                             utable.language,
                                             mtable.pe_id,
                                             )
                    operators = []
                    default_realm_lookups = []
                    for row in users:
                        if row["auth_membership.pe_id"]:
                            # Definite match
                            operators.append(row)
                        else:
                            # Possible Match
                            default_realm_lookups.append(row)

                    user_pe_id = [row["pr_person_user.pe_id"] for row in default_realm_lookups]
                    # Bulk version of s3db.pr_realm()
                    query = (atable.deleted != True) & \
                            (atable.role_id == rtable.id) & \
                            (atable.pe_id.belongs(user_pe_id)) & \
                            (rtable.deleted != True) & \
                            (rtable.role_type == OU) & \
                            (atable.pe_id == ltable.pe_id) & \
                            (ltable.user_id == utable.id)
                    logs_managers_default_realm = db(query).select(ltable.pe_id,
                                                                   utable.language,
                                                                   rtable.pe_id,
                                                                   )
                    for row in logs_managers_default_realm:
                        if row["pr_role.pe_id"] in entities:
                            operators.append(row)

                    if not operators:
                        # Send to ADMIN instead
                        query = (gtable.uuid == "ADMIN") & \
                                (gtable.id == mtable.group_id) & \
                                (mtable.deleted == False) & \
                                (mtable.user_id == utable.id) & \
                                (utable.id == ltable.user_id)
                        operators = db(query).select(ltable.pe_id,
                                                     utable.language,
                                                     )

                # Send Localised Mail(s)
                languages = {}
                for row in operators:
                    language = row["auth_user.language"]
                    if language not in languages:
                        languages[language] = []
                    languages[language].append(row["pr_person_user.pe_id"])
                for language in languages:
                    T.force(language)
                    session_s3.language = language # for date_represent
                    subject = "%s: %s" % (s3_str(subject_T), req_ref)
                    message = s3_str(message_T) % {"date_required": date_represent(date_required),
                                                   "reference": req_ref,
                                                   "site": site_name,
                                                   "url": url,
                                                   }
                    users = languages[language]
                    for pe_id in users:
                        send_email(pe_id,
                                   subject = subject,
                                   message = message,
                                   )

            # Restore language for UI
            session_s3.language = ui_language
            T.force(ui_language)

        session.confirmation = T("Request Approved")
        redirect(URL(args = req_id))

    # -------------------------------------------------------------------------
    @staticmethod
    def req_onaccept(form):
        """
            On-accept actions for requests
                - auto-generate a request number (req_ref) if required and
                  not specified in form
                - translate simple request status into differentiated
                  committed/fulfilled statuses
                - add requester as human resource of the requesting site if
                  configured to do so automatically
                - configure post-create/update redirection depending on request
                  type (e.g. request for items => select items for request)
        """

        db = current.db
        s3db = current.s3db
        settings = current.deployment_settings

        tablename = "req_req"
        table = s3db.req_req

        req_id = form.vars.id
        record = db(table.id == req_id).select(table.id,
                                               table.type,
                                               table.site_id,
                                               table.requester_id,
                                               table.is_template,
                                               table.req_ref,
                                               table.req_status,
                                               table.commit_status,
                                               table.fulfil_status,
                                               table.cancel,
                                               limitby = (0, 1)
                                               ).first()
        if record.is_template:
            is_template = True
            f = "req_template"
        else:
            is_template = False
            f = "req"

            update = {}

            if settings.get_req_use_req_number() and not record.req_ref:
                # Auto-generate req_ref
                code = s3db.supply_get_shipping_code(settings.get_req_shortname(),
                                                     record.site_id,
                                                     table.req_ref,
                                                     )
                update["req_ref"] = code

            req_status = record.req_status
            if req_status is not None:
                status_requires = table.req_status.requires
                if hasattr(status_requires, "other"):
                    status_requires = status_requires.other
                opts = [opt[0] for opt in status_requires.options()]
                if str(REQ_STATUS_CANCEL) in opts:
                    # Cancel flag implied by simple status
                    update["cancel"] = False
                elif record.cancel:
                    # Using explicit cancel flag
                    update["workflow_status"] = 5

                # Translate Simple Status
                if req_status == REQ_STATUS_PARTIAL:
                    if record.commit_status != REQ_STATUS_COMPLETE:
                        update["commit_status"] = REQ_STATUS_PARTIAL
                    if record.fulfil_status == REQ_STATUS_COMPLETE:
                        update["fulfil_status"] = REQ_STATUS_PARTIAL

                elif req_status == REQ_STATUS_COMPLETE:
                    update["fulfil_status"] = REQ_STATUS_COMPLETE

                elif req_status == REQ_STATUS_CANCEL:
                    update["cancel"] = True
                    update["workflow_status"] = 5

                elif req_status == REQ_STATUS_NONE:
                    update["commit_status"] = REQ_STATUS_NONE
                    update["fulfil_status"] = REQ_STATUS_NONE

            elif record.cancel:
                # Using 3-tiered status (commit/transit/fulfill), and explicit cancel flag
                update["workflow_status"] = 5

            if update:
                record.update_record(**update)

        if settings.get_req_requester_to_site():
            requester_id = record.requester_id
            if requester_id:
                site_id = record.site_id
                # If the requester has no HR record, then create one
                hrtable = s3db.hrm_human_resource
                query = (hrtable.person_id == requester_id)
                exists = db(query).select(hrtable.id,
                                          hrtable.organisation_id,
                                          hrtable.site_id,
                                          hrtable.site_contact,
                                          limitby = (0, 1)
                                          ).first()
                if exists:
                    if site_id and not exists.site_id:
                        # Check that the Request site belongs to this Org
                        stable = s3db.org_site
                        site = db(stable.site_id == site_id).select(stable.organisation_id,
                                                                    limitby = (0, 1)
                                                                    ).first()
                        # @ToDo: Think about branches
                        if site and site.organisation_id == exists.organisation_id:
                            # Set the HR record as being for this site
                            exists.update(site_id = site_id)
                            s3db.hrm_human_resource_onaccept(exists)
                elif site_id:
                    # Lookup the Org for the site
                    stable = s3db.org_site
                    site = db(stable.site_id == site_id).select(stable.organisation_id,
                                                                limitby = (0, 1)
                                                                ).first()
                    # Is there already a site_contact for this site?
                    ltable = s3db.hrm_human_resource_site
                    query = (ltable.site_id == site_id) & \
                            (ltable.site_contact == True)
                    already = db(query).select(ltable.id,
                                               limitby = (0, 1)
                                               ).first()
                    if already:
                        site_contact = False
                    else:
                        site_contact = True
                    hr_id = hrtable.insert(person_id = requester_id,
                                           organisation_id = site.organisation_id,
                                           site_id = site_id,
                                           site_contact = site_contact,
                                           )
                    s3db.hrm_human_resource_onaccept(Storage(id = hr_id))

        # Update the Realm if the Requesting site changes
        # - now left to templates
        #if form.record:
        #    if record.site_id != form.record.site_id:
        #        realm_entity = current.auth.get_realm_entity(table, record)
        #        record.update_record(realm_entity = realm_entity)
        #        req_type = record.type
        #        if req_type == 1:
        #            db(s3db.req_req_item.req_id == req_id).update(realm_entity = realm_entity)
        #        #elif req_type == 2:
        #        #    db(s3db.req_req_asset.req_id == req_id).update(realm_entity = realm_entity)
        #        elif req_type == 3:
        #            db(s3db.req_req_skill.req_id == req_id).update(realm_entity = realm_entity)
        #        #elif req_type == 4:
        #        #    db(s3db.req_req_shelter.req_id == req_id).update(realm_entity = realm_entity)

        # Configure the next page to go to based on the request type
        inline_forms = settings.get_req_inline_forms()
        if inline_forms and is_template:
            s3db.configure(tablename,
                           create_next = URL(c="req", f=f,
                                             args = ["[id]", "job"],
                                             ),
                           update_next = URL(c="req", f=f,
                                             args=["[id]", "job"],
                                             ))

        elif not inline_forms:
            req_type = record.type
            if req_type == 1 and settings.has_module("inv"):
                s3db.configure(tablename,
                               create_next = URL(c="req", f=f,
                                                 args = ["[id]", "req_item"],
                                                 ),
                               update_next = URL(c="req", f=f,
                                                 args=["[id]", "req_item"],
                                                 ))
            #elif req_type == 2 and settings.has_module("asset"):
            #    s3db.configure(tablename,
            #                   create_next = URL(c="req", f=f,
            #                                     args = ["[id]", "req_asset"],
            #                                     ),
            #                   update_next = URL(c="req", f=f,
            #                                     args = ["[id]", "req_asset"],
            #                                     ))
            elif req_type == 3 and settings.has_module("hrm"):
                s3db.configure(tablename,
                               create_next = URL(c="req", f=f,
                                                 args = ["[id]", "req_skill"],
                                                 ),
                               update_next = URL(c="req", f=f,
                                                 args = ["[id]", "req_skill"],
                                                 ))
            #elif req_type == 4 and settings.has_module("cr"):
            #    s3db.configure(tablename,
            #                   create_next = URL(c="req", f=f,
            #                                     args = ["[id]", "req_shelter"],
            #                                     ),
            #                   update_next = URL(c="req", f=f,
            #                                     args = ["[id]", "req_shelter"],
            #                                     ))

    # -------------------------------------------------------------------------
    @staticmethod
    def req_req_ondelete(row):
        """
            Remove any scheduled tasks when deleting a recurring request
            template

            Args:
                row: the deleted req_req Row
        """

        db = current.db
        table = db.scheduler_task
        query = (table.function_name == "req_add_from_template") & \
                (table.args == "[%s]" % row.id)
        db(query).delete()

# =============================================================================
class RequestApproverModel(DataModel):
    """
        Model for request approvers
    """

    names = ("req_approver",
             "req_approver_req",
             )

    def model(self):

        T = current.T

        define_table = self.define_table

        person_id = self.pr_person_id

        # -----------------------------------------------------------------
        # Request Approvers
        #
        instance_types = ["org_organisation"] + list(current.auth.org_site_types.keys())
        entity_represent = self.pr_PersonEntityRepresent(show_type = False)

        tablename = "req_approver"
        define_table(tablename,
                     # Could be a Site or Organisation
                     self.super_link("pe_id", "pr_pentity",
                                     label = T("Organization/Site"),
                                     empty = False,
                                     filterby = "instance_type", # Not using instance_types as not a Super-Entity
                                     filter_opts = instance_types,
                                     represent = entity_represent,
                                     readable = True,
                                     writable = True,
                                     # @ToDo: Widget
                                     #widget = S3PentityWidget(),
                                     ),
                     Field("title", # 'position' is a Reserved word in SQL
                           label = T("Position"),
                           ),
                     person_id(),
                     Field("matcher", "boolean",
                           default = False,
                           label = T("Matcher"),
                           represent = s3_yes_no_represent,
                           comment = DIV(_class = "tooltip",
                                         _title = "%s|%s" % (T("Matcher"),
                                                             T("Is this person the one to match request items to specific warehouses &/or purchase them."),
                                                             ))
                           ),
                     CommentsField(),
                     )

        # CRUD strings
        current.response.s3.crud_strings[tablename] = Storage(
            label_create = T("Add Approver"),
            title_display = T("Approver Details"),
            title_list = T("Request Approvers"),
            title_update = T("Edit Approver"),
            label_list_button = T("List Approvers"),
            label_delete_button = T("Delete Approver"),
            msg_record_created = T("Approver added"),
            msg_record_modified = T("Approver updated"),
            msg_record_deleted = T("Approver deleted"),
            msg_list_empty = T("No Approvers currently registered"))

        # -----------------------------------------------------------------
        # Link Approvers <> Requests
        #
        tablename = "req_approver_req"
        define_table(tablename,
                     self.req_req_id(),
                     Field("title", # 'position' is a Reserved word in SQL
                           label = T("Position"),
                           ),
                     person_id(),
                     #CommentsField(),
                     )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

# =============================================================================
class RequestItemModel(DataModel):
    """
        Model for requested items
    """

    names = ("req_req_item",
             "req_item_id",
             "req_item_represent",
             "req_req_item_category",
             )

    def model(self):

        T = current.T
        db = current.db

        settings = current.deployment_settings
        quantities_writable = settings.get_req_item_quantities_writable()
        use_commit = settings.get_req_use_commit()
        show_qty_transit = settings.get_req_show_quantity_transit()
        track_pack_values = settings.get_req_pack_values()

        define_table = self.define_table
        req_id = self.req_req_id

        # -----------------------------------------------------------------
        # Request Items
        #
        tablename = "req_req_item"
        define_table(tablename,
                     req_id(empty = False),
                     self.supply_item_entity_id(),
                     self.supply_item_id(),
                     self.supply_item_pack_id(),
                     Field("quantity", "double", notnull=True,
                           label = T("Quantity"),
                           represent = lambda v: \
                            IS_FLOAT_AMOUNT.represent(v, precision=2),
                           requires = IS_FLOAT_AMOUNT(minimum=1.0),
                           ),
                     Field("pack_value", "double",
                           label = T("Estimated Value per Pack"),
                           readable = track_pack_values,
                           writable = track_pack_values,
                           ),
                     # @ToDo: Move this into a Currency Widget for the pack_value field
                     CurrencyField(readable = track_pack_values,
                                   writable = track_pack_values,
                                   ),
                     # Requested from:
                     self.org_site_id(),
                     Field("quantity_commit", "double",
                           default = 0,
                           label = T("Quantity Committed"),
                           represent = self.req_qnty_commit_represent,
                           requires = IS_FLOAT_AMOUNT(minimum=0.0),
                           readable = use_commit,
                           writable = use_commit and quantities_writable,
                           ),
                     Field("quantity_transit", "double",
                           # FB: I think this is Qty Shipped not remaining in transit
                           # @ToDo: Distinguish between:
                           #        items lost in transit (shipped but not recvd and unlikely to ever be, so still required)
                           #        items still in transit (shipped but not yet recvd but still expected, so no longer need sending)
                           #label = T("Quantity Shipped"),
                           label = T("Quantity in Transit"),
                           represent = self.req_qnty_transit_represent,
                           default = 0,
                           requires = IS_FLOAT_AMOUNT(minimum=0.0),
                           readable = show_qty_transit,
                           writable = show_qty_transit and quantities_writable,
                           ),
                     Field("quantity_fulfil", "double",
                           label = T("Quantity Fulfilled"),
                           represent = self.req_qnty_fulfil_represent,
                           default = 0,
                           requires = IS_FLOAT_AMOUNT(minimum=0.0),
                           writable = quantities_writable,
                           ),
                     Field.Method("pack_quantity",
                                  self.supply_item_pack_quantity(tablename=tablename)
                                  ),
                     CommentsField(),
                     on_define = lambda table: \
                        [table.site_id.set_attributes(label = T("Requested From")),
                         ]
                     )

        # CRUD strings
        current.response.s3.crud_strings[tablename] = Storage(
            label_create = T("Add Item to Request"),
            title_display = T("Request Item Details"),
            title_list = T("Items in Request"),
            title_update = T("Edit Item in Request"),
            label_list_button = T("List Items in Request"),
            label_delete_button = T("Delete Item from Request"),
            msg_record_created = T("Item(s) added to Request"),
            msg_record_modified = T("Item(s) updated on Request"),
            msg_record_deleted = T("Item(s) deleted from Request"),
            msg_list_empty = T("No Items currently requested"))

        # Foreign Key Template
        req_item_represent = req_ReqItemRepresent()
        req_item_id = FieldTemplate("req_item_id", "reference %s" % tablename,
                                    label = T("Request Item"),
                                    ondelete = "CASCADE",
                                    represent = req_item_represent,
                                    requires = IS_EMPTY_OR(
                                                    IS_ONE_OF(db,
                                                              "req_req_item.id",
                                                              req_item_represent,
                                                              orderby = "req_req_item.id",
                                                              sort = True,
                                                              )),
                                    comment = DIV(_class = "tooltip",
                                                  _title = "%s|%s" % (T("Request Item"),
                                                                      T("Select Items from the Request")),
                                                                      ),
                                    script = '''
$.filterOptionsS3({
 'trigger':'req_item_id',
 'target':'item_pack_id',
 'lookupResource':'item_pack',
 'lookupPrefix':'supply',
 'lookupURL':S3.Ap.concat('/req/req_item_packs.json/'),
 'msgNoRecords':i18n.no_packs,
 'fncPrep':S3.supply.fncPrepItem,
 'fncRepresent':S3.supply.fncRepresentItem
})''')

        if settings.get_req_prompt_match():
            # Shows the inventory items which match a requested item
            # @ToDo: Make this page a component of req_item
            create_next = URL(c="req", f="req_item_inv_item",
                              args = ["[id]"],
                              )
        else:
            create_next = None

        list_fields = ["item_id",
                       "item_pack_id",
                       ]
        lappend = list_fields.append
        if settings.get_req_prompt_match():
            lappend("site_id")
        lappend("quantity")
        if use_commit:
            lappend("quantity_commit")
        if show_qty_transit:
            lappend("quantity_transit")
        lappend("quantity_fulfil")
        lappend("comments")

        filter_widgets = [
            OptionsFilter("req_id$fulfil_status",
                          label = T("Status"),
                          options = req_status_opts,
                          cols = 3,
                          ),
            OptionsFilter("req_id$priority",
                          # Better to default (easier to customise/consistency)
                          #label = T("Priority"),
                          options = req_priority_opts,
                          cols = 3,
                          ),
            LocationFilter("req_id$site_id$location_id",
                           ),
            ]

        self.configure(tablename,
                       create_next = create_next,
                       deduplicate = self.req_item_duplicate,
                       deletable = settings.get_req_multiple_req_items(),
                       extra_fields = ["item_pack_id"],
                       filter_widgets = filter_widgets,
                       list_fields = list_fields,
                       onaccept = self.req_item_onaccept,
                       ondelete = self.req_item_ondelete,
                       # @ToDo: default realm to that of the req_id
                       #realm_entity = self.req_item_realm_entity,
                       super_entity = "supply_item_entity",
                       )

        self.add_components(tablename,
                            req_order_item = "req_item_id",
                            )

        # ---------------------------------------------------------------------
        #
        # Req <> Item Category link table
        #
        # - used to provide a search filter
        # - populated onaccept/ondelete of req_item
        #
        tablename = "req_req_item_category"
        define_table(tablename,
                     req_id(empty = False),
                     self.supply_item_category_id(),
                     )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return {"req_item_id": req_item_id,
                "req_item_represent": req_item_represent,
                }

    # -------------------------------------------------------------------------
    def defaults(self):
        """
            Safe defaults for model-global names in case module is disabled
        """

        return {"req_item_id": FieldTemplate.dummy("req_item_id"),
                }

    # -------------------------------------------------------------------------
    @staticmethod
    def req_item_onaccept(form):
        """
            On-accept actions for requested items:
                - update committed/in-transit/fulfilled status of the request
                  when an item is added or quantity changed
                - add item category links for the request when adding an item
                  of a new item category
        """

        db = current.db

        form_vars = form.vars

        req_id = form_vars.get("req_id")
        if not req_id:
            # Reload the record to get the req_id
            record_id = form_vars.get("id")
            table = current.s3db.req_req_item
            record = db(table.id == record_id).select(table.req_id,
                                                      limitby = (0, 1)
                                                      ).first()
            if record:
                req_id = record.req_id

        if not req_id:
            # Item has no req_req context => nothing we can (or need to) do
            return

        # Update Request Status
        req_update_status(req_id)

        # Update req_item_category link table
        item_id = form_vars.get("item_id")
        citable = db.supply_catalog_item
        cats = db(citable.item_id == item_id).select(citable.item_category_id)
        rictable = db.req_req_item_category
        for cat in cats:
            item_category_id = cat.item_category_id
            query = (rictable.deleted == False) & \
                    (rictable.req_id == req_id) & \
                    (rictable.item_category_id == item_category_id)
            exists = db(query).select(rictable.id,
                                      limitby = (0, 1)
                                      )
            if not exists:
                rictable.insert(req_id = req_id,
                                item_category_id = item_category_id,
                                )

    # -------------------------------------------------------------------------
    @staticmethod
    def req_item_ondelete(row):
        """
            On-delete actions for requested items:
                - delete item category links from the request when the last
                  item of a category is removed from the request

            FIXME shouldn't this also update the committed/in-transit/fulfilled
                  status of the request?
        """

        db = current.db
        sitable = db.supply_item
        ritable = db.req_req_item
        item = db(ritable.id == row.id).select(ritable.deleted_fk,
                                               limitby = (0, 1)
                                               ).first()
        fks = json.loads(item.deleted_fk)
        req_id = fks["req_id"]
        item_id = fks["item_id"]
        citable = db.supply_catalog_item
        cats = db(citable.item_id == item_id).select(citable.item_category_id)
        for cat in cats:
            item_category_id = cat.item_category_id
            # Check if we have other req_items in the same category
            query = (ritable.deleted == False) & \
                    (ritable.req_id == req_id) & \
                    (ritable.item_id == sitable.id) & \
                    (sitable.item_category_id == item_category_id)
            others = db(query).select(ritable.id,
                                      limitby = (0, 1)
                                      ).first()
            if not others:
                # Delete req_item_category link table
                rictable = db.req_req_item_category
                query = (rictable.req_id == req_id) & \
                        (rictable.item_category_id == item_category_id)
                db(query).delete()

    # ---------------------------------------------------------------------
    @classmethod
    def req_qnty_commit_represent(cls, quantity, show_link=True):

        return cls.req_quantity_represent(quantity, "commit", show_link)

    # ---------------------------------------------------------------------
    @classmethod
    def req_qnty_transit_represent(cls, quantity, show_link=True):

        return cls.req_quantity_represent(quantity, "transit", show_link)

    # ---------------------------------------------------------------------
    @classmethod
    def req_qnty_fulfil_represent(cls, quantity, show_link=True):

        return cls.req_quantity_represent(quantity, "fulfil", show_link)

    # ---------------------------------------------------------------------
    @staticmethod
    def req_quantity_represent(quantity, qtype, show_link=True):
        """
            TODO better docstring
            TODO There should be better control of this feature - currently this only works
                 with req_items which are being matched by commit / send / recv
        """

        if quantity and show_link and \
           not current.deployment_settings.get_req_item_quantities_writable():
            return TAG[""](quantity,
                           A(DIV(_class = "quantity %s ajax_more collapsed" % qtype
                                 ),
                             _href = "#",
                             )
                           )
        else:
            return quantity

    # -------------------------------------------------------------------------
    @staticmethod
    def req_item_duplicate(item):
        """
            This callback will be called when importing records. It will look
            to see if the record being imported is a duplicate. If the record
            is a duplicate then it will set the item method to update

            Args:
                item: An ImportItem object which includes all the details
                      of the record being imported

            Notes:
                Rules for finding a duplicate:
                - If the Request Number matches
                - The item is the same
        """

        db = current.db

        itable = item.table

        req_id = None
        item_id = None
        for ref in item.references:
            if ref.entry.tablename == "req_req":
                if ref.entry.id != None:
                    req_id = ref.entry.id
                else:
                    uuid = ref.entry.item_id
                    jobitem = item.job.items[uuid]
                    req_id = jobitem.id
            elif ref.entry.tablename == "supply_item":
                if ref.entry.id != None:
                    item_id = ref.entry.id
                else:
                    uuid = ref.entry.item_id
                    jobitem = item.job.items[uuid]
                    item_id = jobitem.id

        if req_id is not None and item_id is not None:
            query = (itable.req_id == req_id) & \
                    (itable.item_id == item_id)
        else:
            return

        duplicate = db(query).select(itable.id,
                                     limitby = (0, 1)
                                     ).first()
        if duplicate:
            item.id = duplicate.id
            item.method = item.METHOD.UPDATE

# =============================================================================
class RequestSkillModel(DataModel):
    """
        Modell for requested skills
    """

    names = ("req_req_skill",
             "req_skill_represent",
             )

    def model(self):

        T = current.T

        settings = current.deployment_settings
        quantities_writable = settings.get_req_skill_quantities_writable()
        use_commit = settings.get_req_use_commit()
        show_transit = settings.get_req_show_quantity_transit()

        # -----------------------------------------------------------------
        # Request Skills
        #
        tablename = "req_req_skill"

        # Context-specific representation of None/[] for multi_skill_id
        multi_skill_represent = S3Represent(lookup = "hrm_skill",
                                            multiple = True,
                                            none = T("No Skills Required"),
                                            )

        self.define_table(tablename,
                          self.req_req_id(empty = False),
                          # Make this a Component
                          #Field("task",
                          #      readable=False,
                          #      writable=False, # Populated from req_req 'Purpose'
                          #      label = T("Task Details")),
                          self.hrm_multi_skill_id(
                                label = T("Required Skills"),
                                comment = T("Leave blank to request an unskilled person"),
                                represent = multi_skill_represent,
                                ),
                          # @ToDo: Add a minimum competency rating?
                          Field("quantity", "integer", notnull=True,
                                default = 1,
                                requires = IS_INT_IN_RANGE(1, None),
                                label = T("Number of People Required"),
                                ),
                          self.org_site_id(),
                          Field("quantity_commit", "integer",
                                label = T("Quantity Committed"),
                                default = 0,
                                requires = IS_INT_IN_RANGE(0, None),
                                readable = use_commit,
                                writable = use_commit and quantities_writable,
                                ),
                          Field("quantity_transit", "integer",
                                label = T("Quantity in Transit"),
                                #represent = lambda quantity_transit: \
                                # req_quantity_represent(quantity_transit,
                                #                        "transit"),
                                default = 0,
                                requires = IS_INT_IN_RANGE(0, None),
                                readable = show_transit,
                                writable = show_transit and quantities_writable,
                                ),
                          Field("quantity_fulfil", "integer",
                                label = T("Quantity Fulfilled"),
                                default = 0,
                                requires = IS_INT_IN_RANGE(0, None),
                                writable = quantities_writable,
                                ),
                          CommentsField(#label = T("Task Details"),
                                        #comment = DIV(_class="tooltip",
                                        #              _title="%s|%s" % (T("Task Details"),
                                        #                                T("Include any special requirements such as equipment which they need to bring.")))
                                        ),
                          on_define = lambda table: \
                            [table.site_id.set_attributes(label = T("Requested From")),
                             ]
                          )

        # CRUD strings
        current.response.s3.crud_strings[tablename] = Storage(
            label_create = T("Add Skill to Request"),
            title_display = T("Requested Skill Details"),
            title_list = T("Requested Skills"),
            title_update = T("Edit Requested Skill"),
            label_list_button = T("List Requested Skills"),
            label_delete_button = T("Remove Skill from Request"),
            msg_record_created = T("Skill added to Request"),
            msg_record_modified = T("Requested Skill updated"),
            msg_record_deleted = T("Skill removed from Request"),
            msg_list_empty = T("No Skills currently requested"))

        list_fields = ["id",
                       "skill_id",
                       # @ToDo: Activate based on a deployment_setting
                       #"task",
                       "quantity",
                       "quantity_transit",
                       "quantity_fulfil",
                       "comments",
                       ]
        if use_commit:
            list_fields.insert(3, "quantity_commit")

        # Filter Widgets
        filter_widgets = [
            OptionsFilter("req_id$fulfil_status",
                          label = T("Status"),
                          options = req_status_opts,
                          cols = 3,
                          ),
            OptionsFilter("req_id$priority",
                          label = T("Priority"),
                          options = req_priority_opts,
                          cols = 3,
                          ),
            LocationFilter("req_id$site_id$location_id",
                           ),
        ]

        # Configuration
        self.configure(tablename,
                       # @ToDo: Produce a custom controller like req_item_inv_item?
                       #create_next = URL(c="req", f="req_skill_skill",
                       #                  args=["[id]"]),
                       deletable = settings.get_req_multiple_req_items(),
                       filter_widgets = filter_widgets,
                       list_fields = list_fields,
                       onaccept = self.req_skill_onaccept,
                       # @ToDo: default realm to that of the req_id
                       #realm_entity = self.req_skill_realm_entity,
                       )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return {"req_skill_represent": self.req_skill_represent,
                }

    # -------------------------------------------------------------------------
    @staticmethod
    def req_skill_onaccept(form):
        """
            On-accept actions for requested items:
                - update committed/in-transit/fulfilled status of the request
                  when a skill is added or quantity changed
                - create a task from the request that people with the requested
                  skill can be assigned to

            Request Status:
                NONE            quantity=0 for all skills
                PARTIAL         quantity>0 but less than requested quantity for
                                at least one skill
                COMPLETE        quantity>=requested quantity for all skills
        """

        db = current.db
        s3db = current.s3db

        form_vars = form.vars

        req_id = form_vars.get("req_id")
        if not req_id:
            # Reload the record to get the req_id
            record_id = form_vars.get("id")
            table = s3db.req_req_item
            record = db(table.id == record_id).select(table.req_id,
                                                      limitby = (0, 1)
                                                      ).first()
            if record:
                req_id = record.req_id

        if not req_id:
            # Item has no req_req context => nothing we can (or need to) do
            return

        rtable = s3db.req_req
        query = (rtable.id == req_id)
        record = db(query).select(rtable.purpose,
                                  limitby = (0, 1)
                                  ).first()

        table = s3db.req_req_skill
        query = (table.req_id == req_id)
        #if record:
        #    # Copy the Task description to the Skills component
        #    db(query).update(task=record.purpose)

        is_none = {"commit": True,
                   "transit": True,
                   "fulfil": True,
                   }

        is_complete = {"commit": True,
                       "transit": True,
                       "fulfil": True,
                       }

        # Must check all skills in the req
        req_skills = db(query).select(table.quantity,
                                      table.quantity_commit,
                                      table.quantity_transit,
                                      table.quantity_fulfil,
                                      )

        for req_skill in req_skills:
            quantity = req_skill.quantity
            for status_type in ["commit", "transit", "fulfil"]:
                if req_skill["quantity_%s" % status_type] < quantity:
                    is_complete[status_type] = False
                if req_skill["quantity_%s" % status_type]:
                    is_none[status_type] = False

        status_update = {}
        for status_type in ["commit", "transit", "fulfil"]:
            if is_complete[status_type]:
                status_update["%s_status" % status_type] = REQ_STATUS_COMPLETE
            elif is_none[status_type]:
                status_update["%s_status" % status_type] = REQ_STATUS_NONE
            else:
                status_update["%s_status" % status_type] = REQ_STATUS_PARTIAL
        query = (rtable.id == req_id)
        db(query).update(**status_update)

        if current.deployment_settings.has_module("project"):
            # Add a Task to which the People can be assigned

            # Get the request record
            otable = s3db.org_site
            query = (rtable.id == req_id) & \
                    (otable.id == rtable.site_id)
            record = db(query).select(rtable.req_ref,
                                      rtable.purpose,
                                      rtable.priority,
                                      rtable.requester_id,
                                      rtable.site_id,
                                      otable.location_id,
                                      limitby = (0, 1)
                                      ).first()
            if not record:
                return

            name = record.req_req.req_ref or "Req: %s" % req_id
            table = s3db.project_task
            task = table.insert(name = name,
                                description = record.req_req.purpose,
                                priority = record.req_req.priority,
                                location_id = record.org_site.location_id,
                                site_id = record.req_req.site_id,
                                )

            # Add the Request as a Component to the Task
            table = s3db.table("req_task_req", None)
            if table:
                table.insert(task_id = task,
                             req_id = req_id)
                # @ToDo: Fire onaccept which may send them a notification?

    # -------------------------------------------------------------------------
    @staticmethod
    def req_skill_represent(record_id):
        """
            Represent a skill request; currently unused

            @ToDo: S3Represent
        """

        if not record_id:
            return current.messages["NONE"]

        db = current.db
        rstable = db.req_req_skill
        hstable = db.hrm_skill
        query = (rstable.id == record_id) & \
                (rstable.skill_id == hstable.id)
        record = db(query).select(hstable.name,
                                  limitby = (0, 1)
                                  ).first()
        try:
            return record.name
        except AttributeError:
            return current.messages.UNKNOWN_OPT

# =============================================================================
class RequestRecurringModel(DataModel):
    """
        Adjuvant model to support request generation by scheduler
    """

    names = ("req_job",
             )

    def model(self):

        T = current.T
        s3 = current.response.s3

        # -----------------------------------------------------------------
        # Jobs for Scheduling Recurring Requests
        #
        tablename = "req_job"
        self.define_table(tablename,
                          self.req_req_id(empty=False),
                          s3.scheduler_task_id(),
                          )

        # CRUD Strings
        s3.crud_strings[tablename] = Storage(
            label_create = T("Create Job"),
            title_display = T("Request Job"),
            title_list = T("Request Schedule"),
            title_update = T("Edit Job"),
            label_list_button = T("List Jobs"),
            msg_record_created = T("Job added"),
            msg_record_modified = T("Job updated"),
            msg_record_deleted = T("Job deleted"),
            msg_list_empty = T("No jobs configured yet"),
            msg_no_match = T("No jobs configured"))

        # Custom Methods
        self.set_method("req_req",
                        component = "job",
                        method = "reset",
                        action = req_job_reset,
                        )

        self.set_method("req_req",
                        component = "job",
                        method = "run",
                        action = req_job_run,
                        )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

# =============================================================================
class RequestNeedsModel(DataModel):
    """
        Simple Requests Management System
        - Starts as Simple free text Needs
        - Extensible via Key-Value Tags
        - Extensible with Items
        - Extensible with Skills
        Use cases:
        - SHARE: local governments express needs to be met by NGOs (/Private Sector/Public in future)
        - Organisations can request Money or Time from remote volunteers
        - Sites can request Time from local volunteers or accept drop-off for Goods
        - Projects can request x (tbc: MapPH usecase)
    """

    names = ("req_need",
             "req_need_id",
             )

    def model(self):

        T = current.T
        db = current.db

        # ---------------------------------------------------------------------
        # Needs
        #
        tablename = "req_need"
        self.define_table(tablename,
                          self.super_link("doc_id", "doc_entity"),
                          self.gis_location_id(), # Can be hidden, e.g. if using Sites (can then sync this onaccept)
                          DateTimeField(default = "now",
                                        widget = "date",
                                        ),
                          DateTimeField("end_date",
                                        label = T("End Date"),
                                        # Enable in Templates if-required
                                        readable = False,
                                        writable = False,
                                        ),
                          req_priority()(),
                          Field("name", notnull = True,
                                length = 64,
                                label = T("Summary of Needs"),
                                requires = [IS_NOT_EMPTY(),
                                            IS_LENGTH(64),
                                            ],
                                ),
                          CommentsField("description",
                                        label = T("Description"),
                                        comment = None,
                                        ),
                          req_status()("status",
                                       label = T("Fulfilment Status"),
                                       ),
                          CommentsField(),
                          )

        # CRUD strings
        current.response.s3.crud_strings[tablename] = Storage(
            label_create = T("Add Needs"),
            title_list = T("Needs"),
            title_display = T("Needs"),
            title_update = T("Edit Needs"),
            title_upload = T("Import Needs"),
            label_list_button = T("List Needs"),
            label_delete_button = T("Delete Needs"),
            msg_record_created = T("Needs added"),
            msg_record_modified = T("Needs updated"),
            msg_record_deleted = T("Needs deleted"),
            msg_list_empty = T("No Needs currently registered"),
            )

        self.configure(tablename,
                       super_entity = "doc_entity",
                       )

        # Components
        self.add_components(tablename,
                            event_event = {"link": "event_event_need",
                                            "joinby": "need_id",
                                            "key": "event_id",
                                            "multiple": False,
                                            },
                            org_organisation = {"link": "req_need_organisation",
                                                "joinby": "need_id",
                                                "key": "organisation_id",
                                                "multiple": False,
                                                },
                            req_need_organisation = {"joinby": "need_id",
                                                     "multiple": False,
                                                     },
                            org_sector = {"link": "req_need_sector",
                                          "joinby": "need_id",
                                          "key": "sector_id",
                                          "multiple": False,
                                          },
                            org_site = {"link": "req_need_site",
                                        "joinby": "need_id",
                                        "key": "site_id",
                                        "multiple": False,
                                        },
                            project_activity = {"link": "req_need_activity",
                                                "joinby": "need_id",
                                                "key": "activity_id",
                                                },
                            req_need_contact = {"joinby": "need_id",
                                                # Can redefine as multiple=True in template if-required
                                                "multiple": False,
                                                },
                            req_need_demographic = "need_id",
                            req_need_item = "need_id",
                            req_need_person = "need_id",
                            req_need_skill = "need_id",
                            req_need_tag = {"name": "tag",
                                            "joinby": "need_id",
                                            },
                            )

        # Custom Methods
        self.set_method("req_need",
                        method = "assign",
                        action = self.pr_AssignMethod(component="need_person"))

        # NB Only instance of this being used (SHARE) over-rides this to show the req_number
        represent = S3Represent(lookup = tablename,
                                show_link = True,
                                )
        need_id = FieldTemplate("need_id", "reference %s" % tablename,
                                label = T("Need"),
                                ondelete = "CASCADE",
                                represent = represent,
                                requires = IS_EMPTY_OR(
                                                IS_ONE_OF(db, "req_need.id",
                                                          represent,
                                                          orderby = "req_need.date",
                                                          sort = True,
                                                          )),
                                sortby = "date",
                                )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return {"req_need_id": need_id,
                }

    # -------------------------------------------------------------------------
    def defaults(self):
        """
            Safe defaults for model-global names in case module is disabled
        """

        return {"req_need_id": FieldTemplate.dummy("need_id"),
                }

# =============================================================================
class RequestNeedsActivityModel(DataModel):
    """
        Simple Requests Management System
        - optional link to Activities (Activity created to respond to Need)
    """

    names = ("req_need_activity",
             )

    def model(self):

        # ---------------------------------------------------------------------
        # Needs <=> Activities
        #

        tablename = "req_need_activity"
        self.define_table(tablename,
                          self.req_need_id(empty = False),
                          self.project_activity_id(empty = False),
                          CommentsField(),
                          )

        self.configure(tablename,
                       deduplicate = S3Duplicate(primary=("need_id",
                                                          "activity_id",
                                                          ),
                                                 ),
                       )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

# =============================================================================
class RequestNeedsContactModel(DataModel):
    """
        Simple Requests Management System
        - optional link to Contacts (People)
    """

    names = ("req_need_contact",
             )

    def model(self):

        T = current.T

        # ---------------------------------------------------------------------
        # Needs <=> Persons
        #

        tablename = "req_need_contact"
        self.define_table(tablename,
                          self.req_need_id(empty = False),
                          self.pr_person_id(empty = False,
                                            label = T("Contact"),
                                            ),
                          CommentsField(),
                          )

        self.configure(tablename,
                       deduplicate = S3Duplicate(primary=("need_id",
                                                          "person_id",
                                                          ),
                                                 ),
                       )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

# =============================================================================
class RequestNeedsDemographicsModel(DataModel):
    """
        Simple Requests Management System
        - optional link to Demographics

        @ToDo: Auto-populate defaults for Items based on Demographics
    """

    names = ("req_need_demographic",
             )

    def model(self):

        T = current.T

        # ---------------------------------------------------------------------
        # Needs <=> Demographics
        #
        if current.s3db.table("stats_demographic"):
            title = current.response.s3.crud_strings["stats_demographic"].label_create
            parameter_id_comment = PopupLink(c = "stats",
                                             f = "demographic",
                                             vars = {"child": "parameter_id"},
                                             title = title,
                                             )
        else:
            parameter_id_comment = None

        tablename = "req_need_demographic"
        self.define_table(tablename,
                          self.req_need_id(empty = False),
                          self.super_link("parameter_id", "stats_parameter",
                                          instance_types = ("stats_demographic",),
                                          label = T("Demographic"),
                                          represent = self.stats_parameter_represent,
                                          readable = True,
                                          writable = True,
                                          empty = False,
                                          comment = parameter_id_comment,
                                          ),
                          req_timeframe(),
                          Field("value", "double",
                                label = T("Number"),
                                #label = T("Number in Need"),
                                represent = lambda v: \
                                    IS_FLOAT_AMOUNT.represent(v, precision=2),
                                requires = IS_NOT_EMPTY(),
                                ),
                          Field("value_committed", "double",
                                label = T("Number Committed"),
                                represent = lambda v: \
                                    IS_FLOAT_AMOUNT.represent(v, precision=2),
                                requires = IS_EMPTY_OR(
                                            IS_FLOAT_AMOUNT(minimum=1.0)),
                                # Enable in templates as-required
                                readable = False,
                                # Normally set automatically
                                writable = False,
                                ),
                          Field("value_uncommitted", "double",
                                label = T("Number Uncommitted"),
                                represent = lambda v: \
                                    IS_FLOAT_AMOUNT.represent(v, precision=2),
                                requires = IS_EMPTY_OR(
                                            IS_FLOAT_AMOUNT(minimum=1.0)),
                                # Enable in templates as-required
                                readable = False,
                                # Normally set automatically
                                writable = False,
                                ),
                          Field("value_reached", "double",
                                label = T("Number Reached"),
                                represent = lambda v: \
                                    IS_FLOAT_AMOUNT.represent(v, precision=2),
                                requires = IS_EMPTY_OR(
                                            IS_FLOAT_AMOUNT(minimum=1.0)),
                                # Enable in templates as-required
                                readable = False,
                                # Normally set automatically
                                writable = False,
                                ),
                          CommentsField(),
                          )

        self.configure(tablename,
                       deduplicate = S3Duplicate(primary=("need_id",
                                                          "parameter_id",
                                                          ),
                                                 ),
                       )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

# =============================================================================
class RequestNeedsItemsModel(DataModel):
    """
        Simple Requests Management System
        - optional extension to support Items, but still not using Inventory-linked Requests
    """

    names = ("req_need_item",
             )

    def model(self):

        T = current.T

        # ---------------------------------------------------------------------
        # Needs <=> Supply Items
        #

        tablename = "req_need_item"
        self.define_table(tablename,
                          self.req_need_id(empty = False),
                          self.supply_item_category_id(),
                          self.supply_item_id(empty = False,
                                              # Default:
                                              #ondelete = "RESTRICT",
                                              # Filter Item dropdown based on Category
                                              script = '''
$.filterOptionsS3({
 'trigger':'item_category_id',
 'target':'item_id',
 'lookupPrefix':'supply',
 'lookupResource':'item',
})''',
                                              # Don't use Auto-complete
                                              widget = None,
                                              ),
                          self.supply_item_pack_id(),
                          req_timeframe(),
                          Field("quantity", "double",
                                label = T("Quantity"),
                                #label = T("Quantity Requested"),
                                represent = lambda v: \
                                    IS_FLOAT_AMOUNT.represent(v, precision=2),
                                requires = IS_EMPTY_OR(
                                            IS_FLOAT_AMOUNT(minimum=1.0)),
                                ),
                          Field("quantity_committed", "double",
                                label = T("Quantity Committed"),
                                represent = lambda v: \
                                    IS_FLOAT_AMOUNT.represent(v, precision=2),
                                requires = IS_EMPTY_OR(
                                            IS_FLOAT_AMOUNT(minimum=1.0)),
                                # Enable in templates as-required
                                readable = False,
                                # Normally set automatically
                                writable = False,
                                ),
                          Field("quantity_uncommitted", "double",
                                label = T("Quantity Uncommitted"),
                                represent = lambda v: \
                                    IS_FLOAT_AMOUNT.represent(v, precision=2),
                                requires = IS_EMPTY_OR(
                                            IS_FLOAT_AMOUNT(minimum=1.0)),
                                # Enable in templates as-required
                                readable = False,
                                # Normally set automatically
                                writable = False,
                                ),
                          Field("quantity_delivered", "double",
                                label = T("Quantity Delivered"),
                                represent = lambda v: \
                                    IS_FLOAT_AMOUNT.represent(v, precision=2),
                                requires = IS_EMPTY_OR(
                                            IS_FLOAT_AMOUNT(minimum=1.0)),
                                # Enable in templates as-required
                                readable = False,
                                # Normally set automatically
                                writable = False,
                                ),
                          req_priority()(),
                          CommentsField(),
                          req_status()("status",
                                       label = T("Fulfilment Status"),
                                       ),
                          )

        self.configure(tablename,
                       deduplicate = S3Duplicate(primary=("need_id",
                                                          "item_id",
                                                          ),
                                                 ),
                       )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

# =============================================================================
class RequestNeedsSkillsModel(DataModel):
    """
        Simple Requests Management System
        - optional extension to support Skills, but still not using normal Requests
    """

    names = ("req_need_skill",
             )

    def model(self):

        T = current.T
        crud_strings = current.response.s3.crud_strings

        # ---------------------------------------------------------------------
        # Needs <=> Skills
        #
        skill_id = self.hrm_skill_id # Load normal model
        CREATE_SKILL = crud_strings["hrm_skill"].label_create

        tablename = "req_need_skill"
        self.define_table(tablename,
                          self.req_need_id(empty = False),
                          skill_id(comment = PopupLink(c = "hrm",
                                                       f = "skill",
                                                       label = CREATE_SKILL,
                                                       tooltip = None,
                                                       vars = {"prefix": "req"},
                                                       ),
                                   empty = False,
                                   ),
                          Field("quantity", "double",
                                label = T("Quantity"),
                                represent = lambda v: \
                                    IS_FLOAT_AMOUNT.represent(v, precision=2),
                                requires = IS_EMPTY_OR(
                                            IS_FLOAT_AMOUNT(minimum=1.0)),
                                ),
                          req_priority()(),
                          CommentsField(),
                          req_status()("status",
                                       label = T("Fulfilment Status"),
                                       ),
                          )

        self.configure(tablename,
                       deduplicate = S3Duplicate(primary=("need_id",
                                                          "skill_id",
                                                          ),
                                                 ),
                       )

        # CRUD strings
        crud_strings[tablename] = Storage(
            label_create = T("Add Skill"),
            title_list = T("Skills"),
            title_display = T("Skill"),
            title_update = T("Edit Skill"),
            #title_upload = T("Import Skills"),
            label_list_button = T("List Skills"),
            label_delete_button = T("Delete Skill"),
            msg_record_created = T("Skill added"),
            msg_record_modified = T("Skill updated"),
            msg_record_deleted = T("Skill deleted"),
            msg_list_empty = T("No Skills currently registered for this Request"),
            )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

# =============================================================================
class RequestNeedsOrganisationModel(DataModel):
    """
        Simple Requests Management System
        - optional link to Organisations
        - link exposed in Templates as-required
    """

    names = ("req_need_organisation",
             )

    def model(self):

        # ---------------------------------------------------------------------
        # Needs <=> Organisations
        #
        organisation_id = self.org_organisation_id # Load normal model
        CREATE = current.response.s3.crud_strings["org_organisation"].label_create

        tablename = "req_need_organisation"
        self.define_table(tablename,
                          self.req_need_id(empty = False),
                          organisation_id(comment = PopupLink(c = "org",
                                                              f = "organisation",
                                                              label = CREATE,
                                                              tooltip = None,
                                                              vars = {"prefix": "req"},
                                                              ),
                                          empty = False,
                                          ),
                          CommentsField(),
                          )

        self.configure(tablename,
                       deduplicate = S3Duplicate(primary=("need_id",
                                                          "organisation_id",
                                                          ),
                                                 ),
                       )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

# =============================================================================
class RequestNeedsPersonModel(DataModel):
    """
        Simple Requests Management System
        - optional link to People (used for assignments to Skills)
        - currently assumes that Need just has a single Skill, so no need to say which skill the person is for
        - used by CCC
    """

    names = ("req_need_person",
             )

    def model(self):

        T = current.T

        # ---------------------------------------------------------------------
        # Needs <=> Persons
        #
        # @ToDo: configuration setting once-required
        status_opts = {1: T("Applied"),
                       2: T("Approved"),
                       3: T("Rejected"),
                       4: T("Invited"),
                       5: T("Accepted"),
                       6: T("Declined"),
                       }

        tablename = "req_need_person"
        self.define_table(tablename,
                          self.req_need_id(empty = False),
                          self.pr_person_id(empty = False),
                          Field("status", "integer",
                                default = 4, # Invited
                                label = T("Status"),
                                represent = represent_option(status_opts),
                                requires = IS_EMPTY_OR(
                                            IS_IN_SET(status_opts)),
                                ),
                          CommentsField(),
                          )

        self.configure(tablename,
                       deduplicate = S3Duplicate(primary=("need_id",
                                                          "person_id",
                                                          ),
                                                 ),
                       )

        current.response.s3.crud_strings[tablename] = Storage(
            label_create = T("Add Person"),
            title_display = T("Person Details"),
            title_list = T("People"),
            title_update = T("Edit Person"),
            #title_upload = T("Import People"),
            label_list_button = T("List People"),
            label_delete_button = T("Remove Person"),
            msg_record_created = T("Person added"),
            msg_record_modified = T("Person updated"),
            msg_record_deleted = T("Person removed"),
            msg_list_empty = T("No People currently linked to this Need")
        )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

# =============================================================================
class RequestNeedsSectorModel(DataModel):
    """
        Simple Requests Management System
        - optional link to Sectors
        - link exposed in Templates as-required
    """

    names = ("req_need_sector",
             )

    def model(self):

        # ---------------------------------------------------------------------
        # Needs <=> Sectors
        #
        tablename = "req_need_sector"
        self.define_table(tablename,
                          self.req_need_id(empty = False),
                          self.org_sector_id(empty = False),
                          CommentsField(),
                          )

        self.configure(tablename,
                       deduplicate = S3Duplicate(primary=("need_id",
                                                          "sector_id",
                                                          ),
                                                 ),
                       )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

# =============================================================================
class RequestNeedsSiteModel(DataModel):
    """
        Simple Requests Management System
        - optional link to Sites
        - link exposed in Templates as-required
    """

    names = ("req_need_site",
             )

    def model(self):

        # ---------------------------------------------------------------------
        # Needs <=> Sites
        #
        SITE = current.deployment_settings.get_org_site_label()

        tablename = "req_need_site"
        self.define_table(tablename,
                          self.req_need_id(empty = False),
                          # Component not instance
                          self.super_link("site_id", "org_site",
                                          label = SITE,
                                          readable = True,
                                          writable = True,
                                          represent = self.org_site_represent,
                                          ),
                          CommentsField(),
                          )

        self.configure(tablename,
                       deduplicate = S3Duplicate(primary=("need_id",
                                                          "site_id",
                                                          ),
                                                 ),
                       )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

# =============================================================================
class RequestNeedsTagModel(DataModel):
    """
        Needs Tags
    """

    names = ("req_need_tag",
             )

    def model(self):

        T = current.T

        # ---------------------------------------------------------------------
        # Need Tags
        # - Key-Value extensions
        # - can be used to add structured extensions, such as:
        #   * Reference
        #   * Cash Donations accepted (/ Details)
        #   * Goods drop-off point (/ Details)
        #   * Transport required (/ Details)
        #   * Security needed (/ Details)
        #   * Volunteering Opportunities (/ Details)
        # - can be used to provide conversions to external systems, such as:
        #   * HXL
        # - can be a Triple Store for Semantic Web support
        #
        tablename = "req_need_tag"
        self.define_table(tablename,
                          self.req_need_id(),
                          # key is a reserved word in MySQL
                          Field("tag",
                                label = T("Key"),
                                ),
                          Field("value",
                                label = T("Value"),
                                ),
                          CommentsField(),
                          )

        self.configure(tablename,
                       deduplicate = S3Duplicate(primary = ("need_id",
                                                            "tag",
                                                            ),
                                                 ),
                       )

        # Pass names back to global scope (s3.*)
        return None

# =============================================================================
class RequestTagModel(DataModel):
    """
        Request Tags
    """

    names = ("req_req_tag",
             )

    def model(self):

        T = current.T

        # ---------------------------------------------------------------------
        # Request Tags
        # - Key-Value extensions
        # - can be used to provide conversions to external systems, such as:
        #   * HXL
        # - can be a Triple Store for Semantic Web support
        #
        tablename = "req_req_tag"
        self.define_table(tablename,
                          self.req_req_id(),
                          # key is a reserved word in MySQL
                          Field("tag",
                                label = T("Key"),
                                ),
                          Field("value",
                                label = T("Value"),
                                ),
                          CommentsField(),
                          )

        self.configure(tablename,
                       deduplicate = S3Duplicate(primary = ("req_id",
                                                            "tag",
                                                            ),
                                                 ),
                       )

        # Pass names back to global scope (s3.*)
        return None

# =============================================================================
class RequestOrderItemModel(DataModel):
    """
        Simple Item Ordering for Requests
        - for when Procurement model isn't being used
    """

    names = ("req_order_item",
             )

    def model(self):

        T = current.T
        NONE = current.messages["NONE"]

        # -----------------------------------------------------------------
        # Request Item Ordering
        #
        tablename = "req_order_item"
        self.define_table(tablename,
                          self.req_item_id(empty = False,
                                           readable = False, # Hidden
                                           writable = False,
                                           ),
                          self.req_req_id(empty = False,
                                          writable = False, # Auto-populated
                                          ),
                          self.supply_item_id(empty = False,
                                              writable = False, # Auto-populated
                                              ),
                          self.supply_item_pack_id(writable = False, # Auto-populated
                                                   ),
                          Field("quantity", "double", notnull=True,
                                default = 0.0,
                                label = T("Quantity"),
                                represent = lambda v: \
                                    IS_FLOAT_AMOUNT.represent(v, precision=2),
                                #requires = IS_FLOAT_AMOUNT(minimum=0.0),
                                writable = False, # Auto-populated
                                ),
                          Field("purchase_ref",
                                label = T("%(PO)s Number") % \
                                    {"PO": current.deployment_settings.get_proc_shortname()},
                                represent = lambda v: v if v else NONE,
                                ),
                          self.inv_recv_id(label = T("Received Shipment"),
                                           ),
                          )

        self.configure(tablename,
                       insertable = False,
                       )

        # CRUD strings
        current.response.s3.crud_strings[tablename] = Storage(
            #label_create = T("Create Purchase Item"),
            title_display = T("Purchase Item Details"),
            title_list = T("Purchase Items"),
            title_update = T("Edit Purchase Item"),
            label_list_button = T("List Purchase Items"),
            label_delete_button = T("Delete Purchase Item"),
            #msg_record_created = T("Purchase Item Added"),
            msg_record_modified = T("Purchase Item Updated"),
            msg_record_deleted = T("Purchase Item Deleted"),
            msg_list_empty = T("No Purchase Items"))

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

# =============================================================================
class RequestProjectModel(DataModel):
    """
        Link Requests to Projects
    """

    names = ("req_project_req",
             )

    def model(self):

        # -----------------------------------------------------------------
        # Link Skill Requests to Tasks
        #
        tablename = "req_project_req"
        self.define_table(tablename,
                          self.project_project_id(empty = False),
                          self.req_req_id(empty = False),
                          )

        self.configure(tablename,
                       deduplicate = S3Duplicate(primary = ("project_id",
                                                            "req_id",
                                                            ),
                                                 ),
                       )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

# =============================================================================
class RequestTaskModel(DataModel):
    """
        Link Requests for Skills to Tasks
    """

    names = ("req_task_req",
             )

    def model(self):

        # -----------------------------------------------------------------
        # Link Skill Requests to Tasks
        #
        tablename = "req_task_req"
        self.define_table(tablename,
                          self.project_task_id(),
                          self.req_req_id(empty=False),
                          #self.req_req_person_id(),
                          #self.req_req_skill_id(),
                          )

        self.configure(tablename,
                       deduplicate = S3Duplicate(primary = ("task_id",
                                                            "req_id",
                                                            ),
                                                 ),
                       )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

# =============================================================================
class RequestRequesterCategoryModel(DataModel):
    """
        Model to control which types of requester can request which items
        - used by RLPPTM
    """

    names = ("req_requester_category",
             )

    def model(self):

        # -----------------------------------------------------------------
        # Link supply item categories to requester attributes (e.g. org type)
        #
        tablename = "req_requester_category"
        self.define_table(tablename,
                          self.supply_item_category_id(
                              empty = False,
                              ondelete = "CASCADE",
                              ),
                          self.org_organisation_type_id(
                              empty = False,
                              ondelete = "CASCADE",
                              ),
                          )

        self.configure(tablename,
                       deduplicate = S3Duplicate(primary = ("item_category_id",
                                                            "organisation_type_id",
                                                            ),
                                                 ),
                       )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

# =============================================================================
class CommitModel(DataModel):
    """
        Model for commits (pledges)
    """

    names = ("req_commit",
             "req_commit_id",
             )

    def model(self):

        T = current.T
        db = current.db
        auth = current.auth

        add_components = self.add_components

        settings = current.deployment_settings

        req_types = settings.get_req_req_type()
        commit_value = settings.get_req_commit_value()
        unsolicited_commit = settings.get_req_commit_without_request()

        # Site/Committer defaults
        committer_is_author = settings.get_req_committer_is_author()
        if committer_is_author:
            site_default = auth.user.site_id if auth.is_logged_in() else None
            committer_default = auth.s3_logged_in_person()
        else:
            site_default = None
            committer_default = None

        # Dropdown or Autocomplete for Committing Site?
        if settings.get_org_site_autocomplete():
            site_widget = S3SiteAutocompleteWidget()
            site_comment = DIV(_class="tooltip",
                               _title="%s|%s" % (T("From Facility"),
                                                 current.messages.AUTOCOMPLETE_HELP,
                                                 ),
                               )
        else:
            site_widget = None
            site_comment = None

        # ---------------------------------------------------------------------
        # Commitments (Pledges)
        #
        tablename = "req_commit"
        self.define_table(tablename,
                          self.super_link("site_id", "org_site",
                                          comment = site_comment,
                                          default = site_default,
                                          label = T("From Facility"),
                                          # Non-Item Requests make False in the prep
                                          readable = True,
                                          writable = True,
                                          represent = self.org_site_represent,
                                          updateable = True,
                                          widget = site_widget,
                                          ),
                          # Used for reporting on where Donations originated
                          self.gis_location_id(readable = False,
                                               writable = False
                                               ),
                          # Non-Item Requests make True in the prep
                          self.org_organisation_id(readable = False,
                                                   writable = False
                                                   ),
                          self.req_req_id(empty = not unsolicited_commit,
                                          ),
                          Field("type", "integer",
                                label = T("Type"),
                                # These are copied automatically from the Req
                                readable = False,
                                writable = False,
                                ),
                          DateTimeField(default = "now",
                                        represent = "date",
                                        ),
                          DateTimeField("date_available",
                                        label = T("Date Available"),
                                        represent = "date",
                                        ),
                          self.pr_person_id("committer_id",
                                            default = committer_default,
                                            label = T("Committed By"),
                                            comment = self.pr_person_comment(child="committer_id"),
                                            ),
                          # @ToDo: Calculate this from line items in Item Commits
                          Field("value", "double",
                                label = T("Estimated Value"),
                                readable = commit_value,
                                writable = commit_value,
                                ),
                          # @ToDo: Move this into a Currency Widget for the value field
                          CurrencyField(readable = commit_value,
                                        writable = commit_value,
                                        ),
                          Field("cancel", "boolean",
                                default = False,
                                label = T("Cancel"),
                                readable = False,
                                writable = False,
                                ),
                          CommentsField(),
                          )

        filter_widgets = [
            TextFilter(["committer_id$first_name",
                        "committer_id$middle_name",
                        "committer_id$last_name",
                        "site_id$name",
                        "comments",
                        "req_id$name",
                        "organisation_id$name"
                        ],
                       label = T("Search"),
                       comment = T("Search for a commitment by Committer name, Request ID, Site or Organization."),
                       ),
            LocationFilter("location_id",
                           hidden = True,
                           ),
            DateFilter("date",
                       # Better to default (easier to customise/consistency)
                       #label = T("Date"),
                       hide_time = True,
                       comment = T("Search for commitments made between these dates."),
                       hidden = True,
                       ),
            DateFilter("date_available",
                       # Better to default (easier to customise/consistency)
                       #label = T("Date Available"),
                       hide_time = True,
                       comment = T("Search for commitments available between these dates."),
                       hidden = True,
                       ),
            ]

        if len(req_types) > 1:
            filter_widgets.insert(1, OptionsFilter("type",
                                                   # Better to default (easier to customise/consistency)
                                                   #label = T("Type"),
                                                   cols = len(req_types),
                                                   hidden = True,
                                                   ))

        # CRUD strings
        current.response.s3.crud_strings[tablename] = Storage(
            label_create = T("Make Commitment"),
            title_display = T("Commitment Details"),
            title_list = T("Commitments"),
            title_update = T("Edit Commitment"),
            label_list_button = T("List Commitments"),
            label_delete_button = T("Delete Commitment"),
            msg_record_created = T("Commitment Added"),
            msg_record_modified = T("Commitment Updated"),
            msg_record_deleted = T("Commitment Canceled"),
            msg_list_empty = T("No Commitments"))

        # Foreign Key Template
        commit_represent = req_CommitRepresent()
        commit_id = FieldTemplate("commit_id", "reference %s" % tablename,
                                  label = T("Commitment"),
                                  ondelete = "CASCADE",
                                  represent = commit_represent,
                                  requires = IS_EMPTY_OR(
                                                IS_ONE_OF(db, "req_commit.id",
                                                          commit_represent,
                                                          orderby = "req_commit.date",
                                                          sort = True,
                                                          )),
                                  sortby = "date",
                                  )

        list_fields = ["site_id",
                       "req_id",
                       "committer_id",
                       ]

        # @ToDo: Allow a single column to support different components based on type
        # @ToDo: Include Qty too (Computed VF in component?)
        if "Stock" in req_types:
            list_fields.append((T("Committed Items"), "commit_item.req_item_id$item_id"))
        if "People" in req_types:
            if settings.get_req_commit_people():
                list_fields.append((T("Committed People"), "commit_person.human_resource_id"))
            else:
                list_fields.append((T("Committed Skills"), "commit_skill.skill_id"))

        list_fields += ["date",
                        "date_available",
                        "comments",
                        ]

        self.configure(tablename,
                       context = {"location": "location_id",
                                  "organisation": "organisation_id",
                                  "request": "req_id",
                                  # We want 'For Sites XX' not 'From Site XX'
                                  #"site": "site_id",
                                  "site": "req_id$site_id",
                                  },
                       filter_widgets = filter_widgets,
                       list_fields = list_fields,
                       # Commitments should only be made to a specific request
                       listadd = unsolicited_commit,
                       onaccept = self.commit_onaccept,
                       ondelete = self.commit_ondelete,
                       )

        # Components
        add_components(tablename,
                       # Committed Items
                       req_commit_item = "commit_id",
                       # Committed Persons
                       req_commit_person = "commit_id",
                       # Committed Skills
                       req_commit_skill = "commit_id",
                       )

        # Custom Method to Assign HRs
        self.set_method("req_commit",
                        method = "assign",
                        action = self.hrm_AssignMethod(component="commit_person",
                                                       next_tab="commit_person",
                                                       ))

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return {"req_commit_id": commit_id,
                }

    # -------------------------------------------------------------------------
    @staticmethod
    def commit_onaccept(form):
        """
            On-accept actions for commits:
                - set location_id and request type
                - update status of request & components
        """

        db = current.db
        s3db = current.s3db

        form_vars = form.vars
        try:
            commit_id = form_vars.id
        except AttributeError:
            return
        if not commit_id:
            return

        ctable = s3db.req_commit
        cdata = {}

        site_id = form_vars.get("site_id")
        if site_id:
            # Set location_id to location of site
            stable = s3db.org_site
            site = db(stable.site_id == site_id).select(stable.location_id,
                                                        limitby = (0, 1)
                                                        ).first()
            if site and site.location_id:
                cdata["location_id"] = site.location_id

        # Find the request
        rtable = s3db.req_req
        query = (ctable.id == commit_id) & \
                (rtable.id == ctable.req_id)
        req = db(query).select(rtable.id,
                               rtable.type,
                               rtable.req_status,
                               rtable.commit_status,
                               limitby = (0, 1)
                               ).first()
        if not req:
            return

        # Update the commit
        cdata["type"] = req.type
        if cdata:
            db(ctable.id == commit_id).update(**cdata)

        # Update committed quantities and request status
        req_update_commit_quantities_and_status(req)

    # -------------------------------------------------------------------------
    @staticmethod
    def commit_ondelete(row):
        """
            Update Status of Request & components
        """

        db = current.db
        s3db = current.s3db
        commit_id = row.id

        # Find the request
        ctable = s3db.req_commit
        fks = db(ctable.id == commit_id).select(ctable.deleted_fk,
                                                limitby = (0, 1)
                                                ).first().deleted_fk
        req_id = json.loads(fks)["req_id"]
        rtable = s3db.req_req
        req = db(rtable.id == req_id).select(rtable.id,
                                             rtable.type,
                                             rtable.commit_status,
                                             limitby = (0, 1)
                                             ).first()
        if not req:
            return

        # Update committed quantities and request status
        req_update_commit_quantities_and_status(req)

# =============================================================================
class CommitItemModel(DataModel):
    """
        Model for committed (pledged) items
    """

    names = ("req_commit_item",
             )

    def model(self):

        T = current.T

        # -----------------------------------------------------------------
        # Commitment Items
        # @ToDo: Update the req_item_id in the commit_item if the req_id of the commit is changed
        #
        tablename = "req_commit_item"
        self.define_table(tablename,
                          self.req_commit_id(),
                          #item_id,
                          #supply_item_id(),
                          self.req_item_id(),
                          self.supply_item_pack_id(),
                          Field("quantity", "double", notnull=True,
                                label = T("Quantity"),
                                ),
                          Field.Method("pack_quantity",
                                       self.supply_item_pack_quantity(tablename=tablename)),
                          CommentsField(),
                          )

        # CRUD strings
        current.response.s3.crud_strings[tablename] = Storage(
            label_create = T("Add Item to Commitment"),
            title_display = T("Commitment Item Details"),
            title_list = T("Commitment Items"),
            title_update = T("Edit Commitment Item"),
            label_list_button = T("List Commitment Items"),
            label_delete_button = T("Delete Commitment Item"),
            msg_record_created = T("Commitment Item added"),
            msg_record_modified = T("Commitment Item updated"),
            msg_record_deleted = T("Commitment Item deleted"),
            msg_list_empty = T("No Commitment Items currently registered"))

        self.configure(tablename,
                       extra_fields = ["item_pack_id"],
                       onaccept = self.commit_item_onaccept,
                       ondelete = self.commit_item_ondelete,
                       )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return {# Used by commit_req() controller (TODO make module-global then?)
                "req_commit_item_onaccept": self.commit_item_onaccept,
                }

    # -------------------------------------------------------------------------
    @staticmethod
    def commit_item_onaccept(form):
        """
            On-accept actions for committed items
                - update the commit quantities and -status of the request
        """

        db = current.db

        try:
            item_id = form.vars.id
        except AttributeError:
            return

        # Get the req
        rtable = db.req_req
        ctable = db.req_commit
        itable = db.req_commit_item
        query = (itable.id == item_id) & \
                (ctable.id == itable.commit_id) & \
                (rtable.id == ctable.req_id)
        req = db(query).select(rtable.id,
                               rtable.type,
                               rtable.req_status,
                               rtable.commit_status,
                               limitby = (0, 1)
                               ).first()
        if not req:
            return

        req_update_commit_quantities_and_status(req)

    # -------------------------------------------------------------------------
    @staticmethod
    def commit_item_ondelete(row):
        """
            On-delete actions for committed items
                - update the commit quantities and -status of the request
        """

        db = current.db
        s3db = current.s3db

        # Get the commit_id
        table = s3db.req_commit_item
        row = db(table.id == row.id).select(table.deleted_fk,
                                            limitby = (0, 1)
                                            ).first()
        try:
            deleted_fk = json.loads(row.deleted_fk)
        except:
            return

        commit_id = deleted_fk.get("commit_id")
        if commit_id:
            ctable = s3db.req_commit
            rtable = s3db.req_req
            query = (ctable.id == commit_id) & \
                    (rtable.id == ctable.req_id)
            req = db(query).select(rtable.id,
                                   rtable.type,
                                   rtable.req_status,
                                   rtable.commit_status,
                                   limitby = (0, 1)
                                   ).first()
            if req:
                req_update_commit_quantities_and_status(req)

# =============================================================================
class CommitPersonModel(DataModel):
    """
        Commit a named individual to a Request

        Used when settings.req.commit_people = True
    """

    names = ("req_commit_person",)

    def model(self):

        T = current.T

        # -----------------------------------------------------------------
        # Committed Persons
        #
        tablename = "req_commit_person"
        self.define_table(tablename,
                          self.req_commit_id(),
                          # For reference
                          #self.hrm_multi_skill_id(comment = None,
                          #                        writable = False,
                          #                        ),
                          # This should be person not hrm as we want to mark
                          # them as allocated across all their Org-affiliations
                          #self.pr_person_id(),
                          # Using HR to use hrm_Assign method (can mark person as allocated onaccept)
                          self.hrm_human_resource_id(),
                          CommentsField(),
                          )

        # CRUD strings
        current.response.s3.crud_strings[tablename] = Storage(
            label_create = T("Add Person to Commitment"),
            title_display = T("Committed Person Details"),
            title_list = T("Committed People"),
            title_update = T("Edit Committed Person"),
            label_list_button = T("List Committed People"),
            label_delete_button = T("Remove Person from Commitment"),
            msg_record_created = T("Person added to Commitment"),
            msg_record_modified = T("Committed Person updated"),
            msg_record_deleted = T("Person removed from Commitment"),
            msg_list_empty = T("No People currently committed"))

        self.configure(tablename,
                       deduplicate = S3Duplicate(primary = ("commit_id",
                                                            "human_resource_id",
                                                            ),
                                                 ),
                       # @ToDo: Fix this before enabling
                       #onaccept = self.commit_person_onaccept,
                       )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

    # -------------------------------------------------------------------------
    @staticmethod
    def commit_person_onaccept(form):
        """
            FIXME not working
        """

        db = current.db
        s3db = current.s3db
        table = db.req_commit_person
        rstable = s3db.req_req_skill

        # Try to get req_skill_id from the form
        req_skill_id = 0
        if form:
            req_skill_id = form.vars.get("req_skill_id", None)
        if not req_skill_id:
            commit_skill_id = get_last_record_id("req_commit_skill")
            r_commit_skill = table[commit_skill_id]
            req_skill_id = r_commit_skill.req_skill_id

        query = (table.req_skill_id == req_skill_id) & \
                (table.deleted == False)
        commit_skills = db(query).select(table.quantity)
        quantity_commit = 0
        for commit_skill in commit_skills:
            quantity_commit += commit_skill.quantity

        r_req_skill = db.req_req_skill[req_skill_id]
        rstable[req_skill_id] = {"quantity_commit": quantity_commit}

        # Update status_commit of the req record
        set_last_record_id("req_req_skill", r_req_skill.id)
        #req_skill_onaccept(None)

# =============================================================================
class CommitSkillModel(DataModel):
    """
        Commit anonymous people to a Request

        Used when settings.req.commit_people = False (default)
    """

    names = ("req_commit_skill",)

    def model(self):

        T = current.T

        # -----------------------------------------------------------------
        # Committed Skills
        #
        tablename = "req_commit_skill"
        self.define_table(tablename,
                          self.req_commit_id(),
                          self.hrm_multi_skill_id(),
                          Field("quantity", "double", notnull=True,
                                label = T("Quantity"),
                                ),
                          CommentsField(),
                          )

        # CRUD strings
        current.response.s3.crud_strings[tablename] = Storage(
            label_create = T("Add People to Commitment"),
            title_display = T("Committed People Details"),
            title_list = T("Committed People"),
            title_update = T("Edit Committed People"),
            label_list_button = T("List Committed People"),
            label_delete_button = T("Remove People from Commitment"),
            msg_record_created = T("People added to Commitment"),
            msg_record_modified = T("Committed People updated"),
            msg_record_deleted = T("People removed from Commitment"),
            msg_list_empty = T("No People currently committed"))

        self.configure(tablename,
                       onaccept = self.commit_skill_onaccept,
                       ondelete = self.commit_skill_ondelete,
                       )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return None

    # -------------------------------------------------------------------------
    @staticmethod
    def commit_skill_onaccept(form):
        """
            On-accept actions for committed skills
                - update the commit quantities and -status of the request
        """

        db = current.db

        try:
            skill_id = form.vars.id
        except AttributeError:
            return

        # Get the req
        rtable = db.req_req
        ctable = db.req_commit
        stable = db.req_commit_skill
        query = (stable.id == skill_id) & \
                (ctable.id == stable.commit_id) & \
                (rtable.id == ctable.req_id)
        req = db(query).select(rtable.id,
                               rtable.type,
                               rtable.req_status,
                               rtable.commit_status,
                               limitby = (0, 1)
                               ).first()
        if not req:
            return

        req_update_commit_quantities_and_status(req)

    # -------------------------------------------------------------------------
    @staticmethod
    def commit_skill_ondelete(row):
        """
            On-delete actions for committed skills
                - update the commit quantities and -status of the request
        """

        db = current.db
        s3db = current.s3db


        # Get the commit_id
        table = s3db.req_commit_skill
        row = db(table.id == row.id).select(table.deleted_fk,
                                            limitby = (0, 1)
                                            ).first()
        try:
            deleted_fk = json.loads(row.deleted_fk)
        except:
            return

        commit_id = deleted_fk.get("commit_id")
        if commit_id:

            ctable = s3db.req_commit
            rtable = s3db.req_req
            query = (ctable.id == commit_id) & \
                    (rtable.id == ctable.req_id)
            req = db(query).select(rtable.id,
                                   rtable.type,
                                   rtable.req_status,
                                   rtable.commit_status,
                                   limitby = (0, 1)
                                   ).first()
            if req:
                req_update_commit_quantities_and_status(req)

# =============================================================================
def req_ref_represent(value, show_link=True, pdf=False):
    """
        Represent for the Request Reference
        if show_link is True then it will generate a link to the record
        if pdf is True then it will generate a link to the PDF

        TODO document parameters
        TODO S3Represent
    """

    if value:
        if show_link:
            db = current.db
            table = db.req_req
            req_row = db(table.req_ref == value).select(table.id,
                                                        limitby = (0, 1)
                                                        ).first()
            if req_row:
                if pdf:
                    args = [req_row.id, "form"]
                else:
                    args = [req_row.id]
                return A(value,
                         _href = URL(c="req", f="req",
                                     args = args,
                                     extension = "",
                                     ),
                         )
        return B(value)

    return current.messages["NONE"]

# -------------------------------------------------------------------------
def req_tabs(r, match=True):
    """
        Add a set of rheader tabs for a site's request management

        Args:
            r: the CRUDRequest (for permission checking)
            match: request matching is applicable for this type of site

        Returns:
            list of rheader tab definitions
    """

    settings = current.deployment_settings

    tabs = []

    if settings.get_org_site_inv_req_tabs():

        has_permission = current.auth.s3_has_permission
        if settings.has_module("req") and \
           has_permission("read", "req_req", c="req"):

            T = current.T

            # Requests tab
            tabs = [(T("Requests"), "req")]

            # Match-tab if applicable for the use-case and user
            # is permitted to match requests
            if match and has_permission("read", "req_req",
                                        c = r.controller,
                                        f = "req_match",
                                        ):
                tabs.append((T("Match Requests"), "req_match/"))

            # Commit-tab if using commits
            if settings.get_req_use_commit():
                tabs.append((T("Commit"), "commit"))

    return tabs

# -----------------------------------------------------------------------------
def req_update_status(req_id):
    """
        Update the request committed/in-transit/fulfilled statuses from the
        quantities of items requested vs. committed/in-transit/fulfilled

        Status:
            NONE            quantity=0 for all items
            PARTIAL         quantity>0 but less than requested quantity for
                            at least one item
            COMPLETE        quantity>=requested quantity for all items
    """

    db = current.db
    s3db = current.s3db
    table = s3db.req_req_item
    is_none = {"commit": True,
               "transit": True,
               "fulfil": True,
               }

    is_complete = {"commit": True,
                   "transit": True,
                   "fulfil": True,
                   }

    # Must check all items in the req (TODO really?)
    query = (table.req_id == req_id) & \
            (table.deleted == False )
    req_items = db(query).select(table.quantity,
                                 table.quantity_commit,
                                 table.quantity_transit,
                                 table.quantity_fulfil,
                                 )

    for req_item in req_items:
        quantity = req_item.quantity
        for status_type in ["commit", "transit", "fulfil"]:
            if req_item["quantity_%s" % status_type] < quantity:
                is_complete[status_type] = False
            if req_item["quantity_%s" % status_type]:
                is_none[status_type] = False

    status_update = {}
    for status_type in ["commit", "transit", "fulfil"]:
        if is_complete[status_type]:
            status_update["%s_status" % status_type] = REQ_STATUS_COMPLETE
        elif is_none[status_type]:
            status_update["%s_status" % status_type] = REQ_STATUS_NONE
        else:
            status_update["%s_status" % status_type] = REQ_STATUS_PARTIAL

    rtable = s3db.req_req
    db(rtable.id == req_id).update(**status_update)

# -------------------------------------------------------------------------
def req_update_commit_quantities_and_status(req):
    """
        Update commit quantities and status of a request

        Args:
            req: the req_req record (Row)
    """

    db = current.db
    s3db = current.s3db
    ctable = s3db.req_commit

    req_id = req.id
    req_type = req.type

    if req_type == 1: # Items

        pack_quantities = s3db.supply_item_pack_quantities

        # Get all commits for this request
        citable = s3db.req_commit_item
        query = (ctable.req_id == req_id) & \
                (citable.commit_id == ctable.id) & \
                (citable.deleted == False)
        citems = db(query).select(citable.item_pack_id,
                                  citable.quantity,
                                  )
        pqty = pack_quantities(item.item_pack_id for item in citems)

        # Determine committed quantities per pack type
        commit_qty = {}
        for item in citems:

            item_pack_id = item.item_pack_id
            committed_quantity = (item.quantity * pqty.get(item_pack_id, 1))

            if item_pack_id in commit_qty:
                commit_qty[item_pack_id] += committed_quantity
            else:
                commit_qty[item_pack_id] = committed_quantity

        ritable = s3db.req_req_item
        query = (ritable.req_id == req_id) & \
                (ritable.deleted == False)
        if not any(qty for qty in commit_qty.values()):
            # Nothing has been committed for this request so far
            commit_status = REQ_STATUS_NONE
            db(query).update(quantity_commit=0)
        else:
            # Get all requested items for this request
            ritems = db(query).select(ritable.id,
                                      ritable.item_pack_id,
                                      ritable.quantity,
                                      ritable.quantity_commit,
                                      )

            pack_ids = (item.item_pack_id for item in ritems
                                          if item.item_pack_id not in pqty)
            pqty.update(pack_quantities(pack_ids))

            # Assume complete unless we find a gap
            commit_status = REQ_STATUS_COMPLETE

            # Update committed quantity for each requested item (if changed),
            # and check if there is still a commit-gap
            for item in ritems:

                committed_quantity = commit_qty.get(item.item_pack_id) or 0
                requested_quantity = item.quantity * pqty.get(item_pack_id, 1)

                if committed_quantity != item.quantity_commit:
                    # Update it
                    item.update_record(quantity_commit=committed_quantity)

                if committed_quantity < requested_quantity:
                    # Gap!
                    commit_status = REQ_STATUS_PARTIAL

        # Update commit-status of the request (if changed)
        if commit_status != req.commit_status:
            req.update_record(commit_status=commit_status)

    elif req_type == 3: # People

        # If this is a single person commitment, then create the
        # commit_person record automatically
        #table = s3db.req_commit_person
        #table.insert(commit_id = commit_id,
        #             #skill_id = ???,
        #             person_id = auth.s3_logged_in_person())
        ## @ToDo: Mark Person's allocation status as 'Committed'

        # Get all commits for this request
        cstable = s3db.req_commit_skill
        query = (ctable.req_id == req_id) & \
                (cstable.commit_id == ctable.id) & \
                (cstable.deleted == False)
        cskills = db(query).select(cstable.skill_id,
                                   cstable.quantity,
                                   )

        rstable = s3db.req_req_skill
        query = (rstable.req_id == req_id) & \
                (rstable.deleted == False)

        if not any(row.quantity for row in cskills):
            # Nothing has been committed for this request so far
            commit_status = REQ_STATUS_NONE
            db(query).update(quantity_commit=0)
        else:
            # Get all requested skill(set)s for this request
            rskills = db(query).select(rstable.id,
                                       rstable.skill_id,
                                       rstable.quantity,
                                       rstable.quantity_commit,
                                       )

            # Match requested and committed skill sets
            # - find the least complex committed skill set to
            #   fulfill a requested skill set
            # - start with most complex requested skill sets
            req_skills = sorted(({"id": row.id,
                                  "skillset": set(row.skill_id),
                                  "requested": row.quantity,
                                  "committed": row.quantity_commit,
                                  } for row in rskills),
                                 key = lambda s: -len(s["skillset"]),
                                 )

            cmt_skills = sorted(({"skillset": set(row.skill_id),
                                  "available": row.quantity,
                                  } for row in cskills),
                                 key = lambda s: len(s["skillset"]),
                                 )

            none = complete = True
            for req_skill_set in req_skills:

                requested_quantity = req_skill_set["requested"]
                quantity_commit = 0

                for cmt_skill_set in cmt_skills:

                    available = cmt_skill_set["available"]
                    required = requested_quantity - quantity_commit
                    if not available or not required:
                        continue

                    if req_skill_set["skillset"] <= cmt_skill_set["skillset"]:

                        # Apply available quantity
                        to_commit = min(required, available)
                        quantity_commit += to_commit
                        cmt_skill_set["available"] -= to_commit

                    if quantity_commit == requested_quantity:
                        break

                # If quantity_commit has changed => update it in the DB
                if quantity_commit != req_skill_set["committed"]:
                    # Update committed quantity
                    db(rstable.id == req_skill_set["id"]).update(quantity_commit = quantity_commit)

                if requested_quantity > quantity_commit:
                    complete = False
                if quantity_commit > 0:
                    none = False

            if none:
                commit_status = REQ_STATUS_NONE
            elif complete:
                commit_status = REQ_STATUS_COMPLETE
            else:
                commit_status = REQ_STATUS_PARTIAL

        if commit_status != req.commit_status:
            req.update_record(commit_status = commit_status)

    elif req_type == 9: # Other

        # Assume Partial not Complete
        # @ToDo: Provide a way for the committer to specify this
        data = {}
        if req.commit_status == REQ_STATUS_NONE:
            data["commit_status"] = REQ_STATUS_PARTIAL
        if req.req_status == REQ_STATUS_NONE:
            # Show as 'Responded'
            data["req_status"] = REQ_STATUS_PARTIAL
        if data:
            req.update_record(**data)

# =============================================================================
def req_req_details(row):
    """
        Field method for requests, representing all requested items/skills
        as string (for use in data tables/lists)
    """

    if hasattr(row, "req_req"):
        row = row.req_req
    try:
        record_id = row.id
        req_type = row.type
    except AttributeError:
        return None

    if req_type == 1:
        s3db = current.s3db
        itable = s3db.supply_item
        ltable = s3db.req_req_item
        query = (ltable.deleted != True) & \
                (ltable.req_id == record_id) & \
                (ltable.item_id == itable.id)
        items = current.db(query).select(itable.name,
                                         ltable.quantity,
                                         )
        if items:
            items = ["%s %s" % (int(item.req_req_item.quantity),
                                item.supply_item.name)
                     for item in items]
            return ",".join(items)

    elif req_type == 3:
        s3db = current.s3db
        ltable = s3db.req_req_skill
        query = (ltable.deleted != True) & \
                (ltable.req_id == record_id)
        skills = current.db(query).select(ltable.skill_id,
                                          ltable.quantity,
                                          )
        if skills:
            represent = S3Represent(lookup="hrm_skill",
                                    multiple=True,
                                    none=current.T("Unskilled")
                                    )
            skills = ["%s %s" % (skill.quantity,
                                 represent(skill.skill_id)) \
                      for skill in skills]
            return ",".join(skills)

    return current.messages["NONE"]

# =============================================================================
def req_req_drivers(row):
    """
        Field method for requests, representing all assigned drivers
        as string (for use in data tables/lists)
    """

    if hasattr(row, "req_req"):
        row = row.req_req
    try:
        req_ref = row.req_ref
        req_type = row.type
    except AttributeError:
        return None

    if req_type == 1:
        s3db = current.s3db
        stable = s3db.inv_send
        query = (stable.deleted != True) & \
                (stable.req_ref == req_ref)
        drivers = current.db(query).select(stable.driver_name,
                                           stable.driver_phone,
                                           stable.vehicle_plate_no,
                                           )
        if drivers:
            drivers = ["%s %s %s" % (driver.driver_name or "",
                                     driver.driver_phone or "",
                                     driver.vehicle_plate_no or "") \
                       for driver in drivers]
            return ",".join(drivers)

    return current.messages["NONE"]

# =============================================================================
def req_rheader(r, check_page=False):
    """
        Resource Header for Requests & Needs

        TODO improve structure/readability
    """

    if r.representation != "html":
        # RHeaders only used in interactive views
        return None

    record = r.record
    if not record:
        # RHeaders only used in single-record views
        return None

    resourcename = r.name
    if resourcename == "req":
        T = current.T
        db = current.db
        s3db = current.s3db
        s3 = current.response.s3
        settings = current.deployment_settings

        is_template = record.is_template
        use_commit = settings.get_req_use_commit()
        use_workflow = settings.get_req_workflow()

        rtype = record.type
        if rtype == 1 and settings.has_module("inv"):
            items = True
            people = False
        elif rtype == 3 and settings.has_module("hrm"):
            items = False
            people = True
        else:
            items = False
            people = False

        site_id = record.site_id
        workflow_status = record.workflow_status

        tabs = [(T("Edit Details"), None)]
        if items:
            if settings.get_req_multiple_req_items():
                req_item_tab_label = T("Items")
            else:
                req_item_tab_label = T("Item")
            tabs.append((req_item_tab_label, "req_item"))
        elif people:
            tabs.append((T("Skills"), "req_skill"))
        #if settings.get_req_document_filing():
        tabs.append((T("Documents"), "document"))
        if is_template:
            tabs.append((T("Schedule"), "job"))
        else:
            # Hide these if no Items/Skills on one of these requests yet
            auth = current.auth
            user = auth.user
            organisation_id = user.organisation_id if user else None

            req_id = record.id
            if items:
                user_site_id = user.site_id if user else None
                ritable = s3db.req_req_item
                possibly_complete = db(ritable.req_id == req_id).select(ritable.id,
                                                                        limitby = (0, 1)
                                                                        )
            elif people:
                rstable = s3db.req_req_skill
                possibly_complete = db(rstable.req_id == req_id).select(rstable.id,
                                                                        limitby = (0, 1)
                                                                        )
            else:
                possibly_complete = True

            if possibly_complete:
                if use_commit:
                    tabs.append((T("Commitments"), "commit"))
                if (items and user_site_id) or \
                   (people and organisation_id and settings.get_req_commit_people()):
                    tabs.append((T("Check"), "check"))
                if use_workflow:
                    if workflow_status == 1: # Draft
                        submit_btn = A(T("Submit for Approval"),
                                       _href = URL(c = "req",
                                                   f = "req",
                                                   args = [req_id, "submit"]
                                                   ),
                                       _id = "req-submit",
                                       _class = "action-btn",
                                       )
                        s3.jquery_ready.append('''S3.confirmClick('#req-submit','%s')''' \
                                % T("Are you sure you want to submit this request?"))
                        s3.rfooter = TAG[""](submit_btn)
                    elif workflow_status == 2: # Submitted
                        if req_is_approver(site_id):
                            # Have they already approved?
                            atable = s3db.req_approver_req
                            query = (atable.req_id == req_id) & \
                                    (atable.person_id == auth.s3_logged_in_person())
                            approved = db(query).select(atable.id,
                                                        limitby = (0, 1)
                                                        )
                            if not approved:
                                approve_btn = A(T("Approve"),
                                               _href = URL(c = "req",
                                                           f = "req",
                                                           args = [req_id, "approve_req"]
                                                           ),
                                               _id = "req-approve",
                                               _class = "action-btn",
                                               )
                                s3.jquery_ready.append('''S3.confirmClick('#req-approve','%s')''' \
                                        % T("Are you sure you want to approve this request?"))
                                s3.rfooter = TAG[""](approve_btn)

        if not check_page:
            rheader_tabs = s3_rheader_tabs(r, tabs)
        else:
            rheader_tabs = DIV()

        if items and r.component and \
                     r.component_name == "commit" and \
                     r.component_id:
            prepare_btn = A(T("Prepare Shipment"),
                            _href = URL(f = "send_commit",
                                        args = [r.component_id]
                                        ),
                            _id = "send-commit",
                            _class = "action-btn",
                            )
            s3.rfooter = TAG[""](prepare_btn)

        if site_id:
            stable = s3db.org_site
        if use_workflow and workflow_status in (1, 2, 5): # Draft/Submitted/Cancelled
            transit_status = ("",)
        elif settings.get_req_show_quantity_transit() and not is_template:
            transit_status = req_status_opts().get(record.transit_status,
                                                   "")
            # @ToDo: Create the 'incoming' function if we need this!
            #if site_id and \
            #   record.transit_status in [REQ_STATUS_PARTIAL, REQ_STATUS_COMPLETE] and \
            #   record.fulfil_status in [None, REQ_STATUS_NONE, REQ_STATUS_PARTIAL]:
            #   site_record = db(stable.site_id == site_id).select(stable.uuid,
            #                                                      stable.instance_type,
            #                                                      limitby = (0, 1)
            #                                                      ).first()
            #   instance_type = site_record.instance_type
            #   table = s3db[instance_type]
            #   query = (table.uuid == site_record.uuid)
            #   instance_id = db(query).select(table.id,
            #                                  limitby = (0, 1)
            #                                  ).first().id
            #   transit_status = SPAN(transit_status,
            #                         A(T("Incoming Shipments"),
            #                           _href = URL(c = instance_type.split("_")[0],
            #                                       f = "incoming",
            #                                       vars = {"viewing" : "%s.%s" % (instance_type, instance_id)}
            #                                       )
            #                           )
            #                      )
            transit_status = (TH("%s: " % T("Transit Status")),
                              transit_status)
        else:
            transit_status = ("",)

        table = r.table

        if settings.get_req_use_req_number() and not is_template:
            headerTR = TR(TH("%s: " % table.req_ref.label),
                          TD(table.req_ref.represent(record.req_ref, show_link=True))
                          )
        else:
            headerTR = TR(TD(settings.get_req_form_name(),
                             _colspan = 2,
                             _class = "pdf_title",
                             ),
                          )
        if site_id:
            org_id = db(stable.site_id == site_id).select(stable.organisation_id,
                                                          limitby = (0, 1)
                                                          ).first().organisation_id
            logo = s3db.org_organisation_logo(org_id)
            if logo:
                headerTR.append(TD(logo,
                                   _colspan = 2,
                                   ))

        if is_template:
            row1 = ""
            row3 = ""
        else:
            if use_workflow and workflow_status in (1, 2, 5): # Draft/Submitted/Cancelled
                row1_status = (TH("%s: " % table.workflow_status.label),
                               table.workflow_status.represent(workflow_status),
                               )
                fulfil_status = ("",)
            else:
                if use_commit:
                    row1_status = (TH("%s: " % table.commit_status.label),
                                   table.commit_status.represent(record.commit_status),
                                   )
                else:
                    row1_status = ("",)
                fulfil_status = (TH("%s: " % table.fulfil_status.label),
                                 table.fulfil_status.represent(record.fulfil_status),
                                 )
            row1 = TR(TH("%s: " % table.date.label),
                      table.date.represent(record.date),
                      *row1_status
                      )
            row3 = TR(TH("%s: " % table.date_required.label),
                      table.date_required.represent(record.date_required),
                      *fulfil_status
                      )

        rheader = DIV(TABLE(headerTR,
                            row1,
                            TR(TH("%s: " % table.site_id.label),
                               table.site_id.represent(site_id),
                               *transit_status
                               ),
                            row3,
                            TR(TH("%s: " % table.requester_id.label),
                               table.requester_id.represent(record.requester_id),
                               ),
                            TR(TH("%s: " % table.purpose.label),
                               record.purpose or current.messages["NONE"],
                               ),
                            TR(TH("%s: " % table.comments.label),
                               TD(record.comments or "",
                                  _colspan = 3,
                                  ),
                               ),
                            ),
                      rheader_tabs,
                      )

    elif resourcename == "need":
        T = current.T
        tabs = [(T("Basic Details"), None),
                (T("Demographics"), "demographic"),
                (T("Items"), "need_item"),
                (T("Skills"), "need_skill"),
                (T("Tags"), "tag"),
                ]

        rheader_tabs = s3_rheader_tabs(r, tabs)

        location_id = r.table.location_id
        rheader = DIV(TABLE(TR(TH("%s: " % location_id.label),
                               location_id.represent(record.location_id),
                               )),
                      rheader_tabs)

    else:
        # Not defined, probably using wrong rheader
        rheader = None

    return rheader

# =============================================================================
def req_match(rheader = None):
    """
        Generic controller to display all requests a site could potentially
        fulfill as a tab of that site instance
            - add as req_match controller to the module, then
            - configure as rheader-tab "req_match/" for the site resource

        Args:
            rheader: module-specific rheader

        Notes:
            - make sure rheader uses s3_rheader_resource to handle "viewing"
            - can override rheader in customise_req_req_controller by
              updating attr dict
    """

    T = current.T
    s3db = current.s3db
    s3 = current.response.s3
    request = current.request
    settings = current.deployment_settings

    output = {}

    viewing = request.get_vars.get("viewing", None)
    if not viewing:
        return output
    if "." in viewing:
        tablename, record_id = viewing.split(".", 1)
    else:
        return output

    # Ensure any custom settings are applied
    customise = settings.get("customise_%s_resource" % tablename)
    if customise:
        try:
            customise(request, tablename)
        except:
            current.log.error("customise_%s_resource is using attributes of r which aren't in request" % tablename)

    table = s3db[tablename]
    row = current.db(table.id == record_id).select(table.site_id,
                                                   limitby = (0, 1)
                                                   ).first()
    if row:
        site_id = row.site_id
    else:
        return output

    actions = [{"label": s3_str(T("Check")),
                "url": URL(c="req", f="req",
                           args = ["[id]", "check"],
                           vars = {"site_id": site_id,
                                   }
                           ),
                "_class": "action-btn",
                }
               ]

    if current.auth.s3_has_permission("update", tablename, record_id):
        # @ToDo: restrict to those which we've not already committed/sent?
        if settings.get_req_use_commit():
            actions.append({"label": s3_str(T("Commit")),
                            "url": URL(c="req", f="commit_req",
                                       args = ["[id]"],
                                       vars = {"site_id": site_id,
                                               }
                                       ),
                            "_class": "action-btn",
                            })
        # Better to force people to go through the Check process
        #actions.append({"label": s3_str(T("Send")),
        #                "url": URL(c="req", f="send_req",
        #                           args = ["[id]"],
        #                           vars = {"site_id": site_id,
        #                                   }
        #                           ),
        #                "_class": "action-btn dispatch",
        #                })

    s3.actions = actions

    if rheader is None:
        if tablename == "org_office":
            rheader = s3db.org_rheader
        elif tablename == "org_facility":
            rheader = s3db.org_facility_rheader
        elif tablename == "inv_warehouse":
            rheader = s3db.inv_rheader
        elif tablename == "cr_shelter":
            rheader = s3db.cr_rheader
        elif tablename == "hms_hospital":
            rheader = s3db.hms_hospital_rheader

    s3.filter = (s3db.req_req.site_id != site_id)
    s3db.configure("req_req",
                   insertable = False,
                   )

    # Pre-process
    def prep(r):
        if settings.get_req_workflow():
            # Only show Approved Requests
            r.resource.add_filter(FS("workflow_status") == 3)

        return True
    s3.prep = prep

    # Post-process
    def postp(r, output):
        if r.representation == "html":
            output["title"] = s3.crud_strings[tablename].title_display
        return output
    s3.postp = postp

    return current.crud_controller("req", "req", rheader=rheader)

# =============================================================================
def req_send_commit():
    """
        Controller function to create a Shipment containing all
        items in a commitment (interactive)
    """

    # Get the commit record
    try:
        commit_id = current.request.args[0]
    except KeyError:
        redirect(URL(c="req", f="commit"))

    db = current.db
    s3db = current.s3db

    req_table = db.req_req
    rim_table = db.req_req_item
    com_table = db.req_commit
    cim_table = db.req_commit_item

    send_table = s3db.inv_send
    tracktable = s3db.inv_track_item

    query = (com_table.id == commit_id) & \
            (com_table.req_id == req_table.id) & \
            (com_table.deleted == False)
    record = db(query).select(com_table.committer_id,
                              com_table.site_id,
                              com_table.organisation_id,
                              req_table.requester_id,
                              req_table.site_id,
                              req_table.req_ref,
                              limitby = (0, 1)
                              ).first()

    # @ToDo: Identify if we have stock items which match the commit items
    # If we have a single match per item then proceed automatically (as-now) & then decrement the stock quantity
    # If we have no match then warn the user & ask if they should proceed anyway
    # If we have mulitple matches then provide a UI to allow the user to select which stock items to use

    # Create an inv_send and link to the commit
    form_vars = Storage(sender_id = record.req_commit.committer_id,
                        site_id = record.req_commit.site_id,
                        recipient_id = record.req_req.requester_id,
                        to_site_id = record.req_req.site_id,
                        req_ref = record.req_req.req_ref,
                        status = 0,
                        )
    send_id = send_table.insert(**form_vars)
    form_vars.id = send_id

    # Get all of the committed items
    query = (cim_table.commit_id == commit_id) & \
            (cim_table.req_item_id == rim_table.id) & \
            (cim_table.deleted == False)
    records = db(query).select(rim_table.id,
                               rim_table.item_id,
                               rim_table.item_pack_id,
                               rim_table.currency,
                               rim_table.quantity,
                               rim_table.quantity_transit,
                               rim_table.quantity_fulfil,
                               cim_table.quantity,
                               )
    # Create inv_track_items for each commit item
    insert = tracktable.insert
    for row in records:
        rim = row.req_req_item
        # Now done as a VirtualField instead (looks better & updates closer to real-time, so less of a race condition)
        #quantity_shipped = max(rim.quantity_transit, rim.quantity_fulfil)
        #quantity_needed = rim.quantity - quantity_shipped
        insert(req_item_id = rim.id,
               track_org_id = record.req_commit.organisation_id,
               send_id = send_id,
               status = 1,
               item_id = rim.item_id,
               item_pack_id = rim.item_pack_id,
               currency = rim.currency,
               #req_quantity = quantity_needed,
               quantity = row.req_commit_item.quantity,
               recv_quantity = row.req_commit_item.quantity,
               )

    # Create the Waybill
    form = Storage()
    form.vars = form_vars
    s3db.inv_send_onaccept(form)

    # Redirect to inv_send for the send id just created
    redirect(URL(#c = "inv", or "req"
                 f = "send",
                 #args = [send_id, "track_item"]
                 args = [send_id]
                 ))

# =============================================================================
class req_CheckMethod(CRUDMethod):
    """
        Check to see if you can match a Request
            - Using the Inventory of your Site if this is an Items request
            - Using the Skills of your HRs if this is a Skills request
    """

    # -------------------------------------------------------------------------
    def apply_method(self, r, **attr):
        """
            Applies the method (controller entry point).

            Args:
                r: the CRUDRequest
                attr: controller options for this request
        """

        req_type = r.record.type
        if req_type == 1:
            return self.inv_match(r, **attr)
        elif req_type == 3:
            return self.skills_match(r, **attr)
        else:
            r.error(405, current.ERROR.BAD_METHOD)

    # -------------------------------------------------------------------------
    @staticmethod
    def inv_match(r, **attr):
        """
            Match a Request's Items with a Site's Inventory
        """

        T = current.T
        db = current.db
        s3db = current.s3db
        response = current.response
        s3 = response.s3

        output = {"title": T("Check Request"),
                  "rheader": req_rheader(r, check_page=True),
                  "subtitle": T("Requested Items"),
                  }

        # Read req_items
        table = s3db.req_req_item
        query = (table.req_id == r.id ) & \
                (table.deleted == False )
        req_items = db(query).select(table.id,
                                     table.item_id,
                                     table.quantity,
                                     table.item_pack_id,
                                     table.quantity_commit,
                                     table.quantity_transit,
                                     table.quantity_fulfil,
                                     )

        if len(req_items):
            site_id = r.get_vars.get("site_id") or current.auth.user.site_id

            if site_id:
                site_name = s3db.org_site_represent(site_id, show_link=False)
                qty_in_label = s3_str(T("Quantity in %s")) % site_name
            else:
                qty_in_label = T("Quantity Available")

            # Build the Output Representation
            row = TR(TH(table.item_id.label),
                     TH(table.quantity.label),
                     TH(table.item_pack_id.label),
                     #TH(table.quantity_transit.label),
                     #TH(table.quantity_fulfil.label),
                     TH(T("Quantity Oustanding")),
                     TH(qty_in_label),
                     TH(T("Match?"))
                     )
            #use_commit = current.deployment_settings.get_req_use_commit()
            #if use_commit:
            #    row.insert(3, TH(table.quantity_commit.label))
            items = TABLE(THEAD(row),
                          _id = "list",
                          _class = "dataTable display",
                          )
            if site_id:
                stable = s3db.org_site
                ltable = s3db.gis_location
                query = (stable.id == site_id) & \
                        (stable.location_id == ltable.id)
                location_r = db(query).select(ltable.lat,
                                              ltable.lon,
                                              limitby = (0, 1)
                                              ).first()
                query = (stable.id == r.record.site_id ) & \
                        (stable.location_id == ltable.id)
                req_location_r = db(query).select(ltable.lat,
                                                  ltable.lon,
                                                  limitby = (0, 1)
                                                  ).first()

                try:
                    distance = current.gis.greatCircleDistance(location_r.lat,
                                                               location_r.lon,
                                                               req_location_r.lat,
                                                               req_location_r.lon)
                    output["rheader"][0].append(TR(TH(s3_str(T("Distance from %s:")) % site_name,
                                                      ),
                                                   TD(T("%.1f km") % distance)
                                                   ))
                except:
                    pass

                if len(req_items):
                    # Get inv_items from this site which haven't expired and are in good condition
                    iitable = s3db.inv_inv_item
                    query = (iitable.site_id == site_id) & \
                            (iitable.deleted == False) & \
                            ((iitable.expiry_date >= r.now) | ((iitable.expiry_date == None))) & \
                            (iitable.status == 0)
                    inv_items_dict = {}
                    inv_items = db(query).select(iitable.item_id,
                                                 iitable.quantity,
                                                 iitable.item_pack_id,
                                                 # VF
                                                 #iitable.pack_quantity,
                                                 )
                    for item in inv_items:
                        item_id = item.item_id
                        if item_id in inv_items_dict:
                            inv_items_dict[item_id] += item.quantity * item.pack_quantity()
                        else:
                            inv_items_dict[item_id] = item.quantity * item.pack_quantity()

                    supply_item_represent = table.item_id.represent
                    item_pack_represent = table.item_pack_id.represent
                    no_match = True
                    for req_item in req_items:
                        req_quantity = req_item.quantity
                        # Do we have any outstanding quantity?
                        quantity_outstanding = req_quantity - max(req_item.quantity_fulfil, req_item.quantity_transit)
                        if quantity_outstanding:
                            # Convert Packs inv item quantity to req item quantity
                            item_id = req_item.item_id
                            if item_id in inv_items_dict:
                                inv_quantity = inv_items_dict[item_id] / req_item.pack_quantity()
                            else:
                                inv_quantity = 0

                            if inv_quantity != 0:
                                no_match = False
                                if inv_quantity < req_quantity:
                                    status = SPAN(T("Partial"), _class="req_status_partial")
                                else:
                                    status = SPAN(T("YES"), _class="req_status_complete")
                            else:
                                status = SPAN(T("NO"), _class="req_status_none")
                        else:
                            inv_quantity = T("N/A")
                            status = SPAN(T("N/A"), _class="req_status_none")

                        items.append(TR(#A(req_item.id),
                                        supply_item_represent(req_item.item_id),
                                        req_quantity,
                                        item_pack_represent(req_item.item_pack_id),
                                        # This requires an action btn to get the req_id
                                        #req_item.quantity_commit, # if use_commit
                                        #req_item.quantity_transit,
                                        #req_item.quantity_fulfil,
                                        #req_quantity_represent(req_item.quantity_commit, "commit"), # if use_commit
                                        #req_quantity_represent(req_item.quantity_fulfil, "fulfil"),
                                        #req_quantity_represent(req_item.quantity_transit, "transit"),
                                        quantity_outstanding,
                                        inv_quantity,
                                        status,
                                        )
                                     )

                    #s3.actions = [req_item_inv_item_btn]
                    if no_match:
                        response.warning = s3_str(T("%(site_name)s has no items exactly matching this request. Use Alternative Items if wishing to use other items to fulfill this request!") %
                                                  {"site_name": site_name})
                    else:
                        commit_btn = A(s3_str(T("Send from %s")) % site_name,
                                       _href = URL(#c = "inv", or "req"
                                                   #c = "req",
                                                   f = "send_req",
                                                   args = [r.id],
                                                   vars = {"site_id": site_id}
                                                   ),
                                       _class = "action-btn"
                                       )
                        s3.rfooter = TAG[""](commit_btn)

            else:
                response.error = T("User has no Site to check against!")

            output["items"] = items
            s3.no_sspag = True # pag won't work
            s3.no_formats = True

        else:
            output["items"] = s3.crud_strings.req_req_item.msg_list_empty

        response.view = "list.html"

        return output

    # -------------------------------------------------------------------------
    @staticmethod
    def skills_match(r, **attr):
        """
            Match a Request's Skills with an Organisation's HRs

            @ToDo: Optionally Filter by Site
                (Volunteers don't currently link to a Site)
            @ToDo: Check Availability
                    - when the Volunteer has said they will work
                    - where the Volunteer has said they will work
                    - don't commit the same time slot twice
        """

        T = current.T
        db = current.db
        s3db = current.s3db
        response = current.response
        s3 = response.s3

        output = {"title": T("Check Request"),
                  "rheader": req_rheader(r, check_page=True),
                  "subtitle": T("Requested Skills"),
                  }

        # Read req_skills
        table = s3db.req_req_skill
        query = (table.req_id == r.id ) & \
                (table.deleted == False )
        req_skills_multi = db(query).select(table.id,
                                            table.skill_id,
                                            table.quantity,
                                            table.quantity_commit,
                                            table.quantity_transit,
                                            table.quantity_fulfil,
                                            )

        if len(req_skills_multi):
            organisation_id = r.get_vars.get("organisation_id") or \
                              current.auth.user.organisation_id

            if organisation_id:
                org_name = s3db.org_organisation_represent(organisation_id,
                                                           show_link=False)
                qty_in_label = s3_str(T("Quantity in %s")) % org_name
            else:
                qty_in_label = T("Quantity Available")

            # Build the Output Representation
            row = TR(TH(table.skill_id.label),
                     TH(table.quantity.label),
                     #TH(table.quantity_transit.label),
                     #TH(table.quantity_fulfil.label),
                     TH(T("Quantity Oustanding")),
                     TH(qty_in_label),
                     TH(T("Match?"))
                     )
            #use_commit = current.deployment_settings.get_req_use_commit()
            #if use_commit:
            #    row.insert(3, TH(table.quantity_commit.label))
            items = TABLE(THEAD(row),
                          _id="list",
                          _class="dataTable display",
                          )

            if organisation_id:

                req_skills = []
                for row in req_skills_multi:
                    skills_multi = row.skill_id
                    for skill_id in skills_multi:
                        if skill_id not in req_skills:
                            req_skills.append(skill_id)

                # Get the People from this Org with at least one of the Requested Skills
                # NB This isn't exact yet since we may need people to have multiple skills
                htable = s3db.hrm_human_resource
                #ptable = s3db.pr_person
                ctable = s3db.hrm_competency
                query = (htable.organisation_id == organisation_id) & \
                        (htable.deleted == False) & \
                        (htable.person_id == ctable.person_id) & \
                        (ctable.deleted == False) & \
                        (ctable.skill_id.belongs(req_skills))
                skills = db(query).select(htable.id,
                                          ctable.skill_id,
                                          )
                people = {}
                for s in skills:
                    hr_id = s[htable.id]
                    if hr_id in people:
                        people[hr_id].append(s[ctable.skill_id])
                    else:
                        people[hr_id] = [s[ctable.skill_id]]

                multi_skill_represent = table.skill_id.represent
                no_match = True
                for req_skill in req_skills_multi:
                    skills = req_skill.skill_id
                    req_quantity = req_skill.quantity
                    # Do we have any outstanding quantity?
                    quantity_outstanding = req_quantity - max(req_skill.quantity_fulfil, req_skill.quantity_transit)
                    if quantity_outstanding:
                        len_skills = len(skills)
                        matches = []
                        for p in people:
                            smatches = 0
                            for s in skills:
                                if s in people[p]:
                                    smatches += 1
                            if smatches == len_skills:
                                matches.append(p)
                        org_quantity = len(matches)
                        if org_quantity != 0:
                            no_match = False
                            if org_quantity < req_quantity:
                                status = SPAN(T("Partial"), _class="req_status_partial")
                            else:
                                status = SPAN(T("YES"), _class="req_status_complete")
                        else:
                            status = SPAN(T("NO"), _class="req_status_none")
                    else:
                        org_quantity = T("N/A")
                        status = SPAN(T("N/A"), _class="req_status_none")

                    items.append(TR(#A(req_item.id),
                                    multi_skill_represent(skills),
                                    req_quantity,
                                    # This requires an action btn to get the req_id
                                    #req_skill.quantity_commit, # if use_commit
                                    #req_skill.quantity_transit,
                                    #req_skill.quantity_fulfil,
                                    #req_quantity_represent(req_skill.quantity_commit, "commit"), # if use_commit
                                    #req_quantity_represent(req_skill.quantity_fulfil, "fulfil"),
                                    #req_quantity_represent(req_skill.quantity_transit, "transit"),
                                    quantity_outstanding,
                                    org_quantity,
                                    status,
                                    )
                                 )

                if not no_match:
                    commit_btn = A(T("Assign People to this Request"),
                                   _href = URL(c = "req",
                                               f = "req",
                                               args = [r.id, "commit_all", "assign"],
                                               ),
                                   _class = "action-btn"
                                   )
                    s3.rfooter = TAG[""](commit_btn)
            else:
                response.error = T("User has no Organization to check against!")

            output["items"] = items
            s3.no_sspag = True # pag won't work
            s3.no_formats = True

        else:
            output["items"] = s3.crud_strings.req_req_skill.msg_list_empty

        response.view = "list.html"

        return output

# =============================================================================
class req_RequesterRepresent(S3Represent):
    """
        Representation of the requester_id, incl. mobile phone number
        and link to contacts tab of the person.
    """

    def __init__(self, show_link=True):
        """
            Args:
                show_link: render as link to the contact tab of
                           the requester (in PR/HRM/VOL as appropriate)
        """

        super().__init__(lookup = "pr_person",
                         show_link = show_link,
                         )

    # -------------------------------------------------------------------------
    def lookup_rows(self, key, values, fields=None):
        """
            Custom look-up of rows

            Args:
                key: the key field
                values: the values to look up
                fields: unused (retained for API compatibility)
        """

        s3db = current.s3db

        ptable = self.table

        count = len(values)
        if count == 1:
            query = (ptable.id == values[0])
        else:
            query = (ptable.id.belongs(values))

        ctable = s3db.pr_contact
        left = [ctable.on((ctable.pe_id == ptable.pe_id) & \
                          (ctable.contact_method == "SMS")),
                ]
        fields = [ptable.id,
                  ptable.first_name,
                  ptable.middle_name,
                  ptable.last_name,
                  ctable.value,
                  ]

        if current.deployment_settings.has_module("hrm"):
            htable = s3db.hrm_human_resource
            left.append(htable.on(htable.person_id == ptable.id))
            fields.append(htable.type)

        rows = current.db(query).select(left = left,
                                        limitby = (0, count),
                                        *fields)
        self.queries += 1
        return rows

    # -------------------------------------------------------------------------
    def represent_row(self, row):
        """
            Represent a row

            Args:
                row: the Row
        """

        if not hasattr(row, "pr_person"):
            return s3_fullname(row)

        person = row.pr_person
        reprstr = s3_fullname(person)
        if hasattr(row, "pr_contact"):
            try:
                contact = row.pr_contact.value
            except AttributeError:
                pass
            else:
                if contact:
                    reprstr = "%s %s" % (s3_str(reprstr), s3_str(contact))

        return reprstr

    # -------------------------------------------------------------------------
    def link(self, k, v, row=None):
        """
            Represent a (key, value) as hypertext link.

            Args:
                k: the key
                v: the representation of the key
                row: the row with this key
        """

        hr_type = None

        if row and hasattr(row, "hrm_human_resource"):
            try:
                hr_type = row.hrm_human_resource.type
            except AttributeError:
                pass

        if hr_type == 1:
            controller = "hrm"
        elif hr_type == 2:
            controller = "vol"
        else:
            controller = "pr"

        return A(v,
                 _href=URL(c = controller,
                           f = "person",
                           args = [k, "contacts"],
                           ),
                 )

# =============================================================================
class req_ReqItemRepresent(S3Represent):

    def __init__(self):

        super().__init__(lookup = "req_req_item",
                         )

    # -------------------------------------------------------------------------
    def lookup_rows(self, key, values, fields=None):
        """
            Custom look-up of rows

            Args:
                key: the key field
                values: the values to look up
                fields: unused (retained for API compatibility)
        """

        ritable = self.table
        sitable = current.s3db.supply_item

        count = len(values)
        if count == 1:
            query = (ritable.id == values[0])
        else:
            query = (ritable.id.belongs(values))

        left = sitable.on(ritable.item_id == sitable.id)
        rows = current.db(query).select(ritable.id,
                                        sitable.name,
                                        left = left,
                                        limitby = (0, count)
                                        )
        self.queries += 1
        return rows

    # -------------------------------------------------------------------------
    def represent_row(self, row):
        """
            Represent a row

            Args:
                row: the Row
        """

        if not hasattr(row, "supply_item"):
            return str(row.id)

        return row.supply_item.name

# =============================================================================
class req_CommitRepresent(S3Represent):
    """
        Represent a commit
    """

    def __init__(self):

        super().__init__(lookup = "req_commit",
                         )

    # -------------------------------------------------------------------------
    def lookup_rows(self, key, values, fields=None):
        """
            Custom look-up of rows

            Args:
                key: the key field
                values: the values to look up
                fields: unused (retained for API compatibility)
        """

        table = self.table

        count = len(values)
        if count == 1:
            query = (table.id == values[0])
        else:
            query = (table.id.belongs(values))

        rows = current.db(query).select(table.id,
                                        table.type,
                                        table.date,
                                        table.organisation_id,
                                        table.site_id,
                                        limitby = (0, count)
                                        )
        self.queries += 1

        # Collect site_ids/organisation_ids after commit type
        organisation_ids = set()
        site_ids = set()
        for row in rows:
            if row.type == 1:
                site_ids.add(row.site_id)
            else:
                organisation_ids.add(row.organisation_id)

        # Bulk-represent site_ids
        if site_ids:
            represent = table.site_id.represent
            if represent and hasattr(represent, "bulk"):
                represent.bulk(list(site_ids))

        # Bulk-represent organisation_ids
        if organisation_ids:
            represent = table.organisation_id.represent
            if represent and hasattr(represent, "bulk"):
                represent.bulk(list(organisation_ids))

        return rows

    # -------------------------------------------------------------------------
    def represent_row(self, row):
        """
            Represent a row

            Args:
                row: the Row
        """

        table = self.table

        try:
            commit_type = row.type
        except AttributeError:
            # Unknown commit type => assume "other"
            commit_type = None

        # Determine the committer field and id after commit type
        if commit_type == 1:
            field = table.site_id
            committer_id = row.site_id
        else:
            field = table.organisation_id
            committer_id = row.organisation_id

        # Represent the committer (site or org)
        if committer_id and field.represent:
            committer = field.represent(committer_id)
        else:
            committer = None

        # Represent the commit date
        if row.date:
            daterepr = table.date.represent(row.date)
        else:
            daterepr = T("undated")

        # Combine committer/date as available
        if committer:
            if isinstance(committer, DIV):
                reprstr = TAG[""](committer, " - ", daterepr)
            else:
                reprstr = "%s - %s" % (committer, daterepr)
        else:
            reprstr = daterepr

        return reprstr

# =============================================================================
def req_job_reset(r, **attr):
    """
        Reset a job status from FAILED to QUEUED (custom REST method),
        for "Reset" action button
    """

    if r.interactive:
        if r.component and r.component.alias == "job":
            job_id = r.component_id
            if job_id:
                S3Task.reset(job_id)
                current.session.confirmation = current.T("Job reactivated")

    redirect(r.url(method="", component_id=0))

# =============================================================================
def req_job_run(r, **attr):
    """
        Run a job now (custom REST method),
        for "Run Now" action button
    """

    if r.interactive:
        if r.id:
            current.s3task.run_async("req_add_from_template",
                                     [r.id], # args
                                     {"user_id":current.auth.user.id} # vars
                                     )
            current.session.confirmation = current.T("Request added")

    redirect(r.url(method="", component_id=0))

# =============================================================================
def req_add_from_template(req_id):
    """
        Add a Request from a Template (scheduled function to create
        recurring requests)

        Args:
            req_id: record ID of the request template
    """

    fieldnames = ["type",
                  "priority",
                  "site_id",
                  "purpose",
                  "requester_id",
                  "comments",
                  ]
    db = current.db
    s3db = current.s3db
    table = s3db.req_req
    fields = [table[field] for field in fieldnames]

    # Load Template
    template = db(table.id == req_id).select(limitby = (0, 1),
                                             *fields
                                             ).first()
    data = {"is_template": False}
    try:
        for field in fieldnames:
            data[field] = template[field]
    except TypeError as e:
        raise RuntimeError("Template not found: %s" % req_id) from e

    settings = current.deployment_settings
    if settings.get_req_use_req_number():
        code = s3db.supply_get_shipping_code(settings.get_req_shortname(),
                                             template.site_id,
                                             table.req_ref,
                                             )
        data["req_ref"] = code

    new_req_id = table.insert(**data)

    if template.type == 1:
        # Copy across req_item
        table = s3db.req_req_item
        fieldnames = ["site_id",
                      "item_id",
                      "item_pack_id",
                      "quantity",
                      "pack_value",
                      "currency",
                      "comments",
                      ]
        fields = [table[field] for field in fieldnames]
        items = db(table.req_id == req_id).select(*fields)
        for item in items:
            data = {"req_id": new_req_id}
            for field in fieldnames:
                data[field] = item[field]
            table.insert(**data)

    elif template.type == 3:
        # Copy across req_skill
        table = s3db.req_req_skill
        fieldnames = ["site_id",
                      "task",
                      "skill_id",
                      "quantity",
                      "comments",
                      ]
        fields = [table[field] for field in fieldnames]
        skills = db(table.req_id == req_id).select(*fields)
        for skill in skills:
            data = {"req_id": new_req_id}
            for field in fieldnames:
                data[field] = skill[field]
            table.insert(**data)

    return new_req_id

# =============================================================================
def req_is_approver(site_id):
    """
        Check if User has permission to Approve a Request
    """

    auth = current.auth

    # Will cause issues
    #if auth.s3_has_role("ADMIN"):
    #    return True

    db = current.db
    s3db = current.s3db
    atable = s3db.req_approver
    query = (atable.person_id == auth.s3_logged_in_person()) & \
            (atable.deleted == False)
    entities = db(query).select(atable.pe_id)
    if not entities:
        # Not an Approver for any
        return False

    pe_ids = [row.pe_id for row in entities]

    stable = s3db.org_site
    site_entity = db(stable.site_id == site_id).select(stable.instance_type,
                                                       limitby = (0, 1)
                                                       ).first()
    itable = s3db.table(site_entity.instance_type)
    site = db(itable.site_id == site_id).select(itable.pe_id,
                                                limitby = (0, 1)
                                                ).first()

    pe_id = site.pe_id
    if pe_id in pe_ids:
        # Directly permitted
        return True

    # Check for child entities
    entity_types = ["org_organisation"] + list(auth.org_site_types.keys())
    child_pe_ids = s3db.pr_get_descendants(pe_ids, entity_types=entity_types)
    if pe_id in child_pe_ids:
        # Permitted via child entity
        return True

    return False

# =============================================================================
def req_approvers(site_id):
    """
        Return people permitted to Approve a Request
    """

    db = current.db
    s3db = current.s3db

    stable = s3db.org_site
    site_entity = db(stable.site_id == site_id).select(stable.instance_type,
                                                       limitby = (0, 1)
                                                       ).first()
    itable = s3db.table(site_entity.instance_type)
    site = db(itable.site_id == site_id).select(itable.pe_id,
                                                limitby = (0, 1)
                                                ).first()

    pe_id = site.pe_id
    entities = s3db.pr_get_ancestors(pe_id)
    entities.append(pe_id)

    atable = s3db.req_approver
    query = (atable.pe_id.belongs(entities)) & \
            (atable.deleted == False)
    approvers = db(query).select(atable.person_id,
                                 atable.title,
                                 atable.matcher,
                                 )

    return {row.person_id: {"title": row.title,
                            "matcher": row.matcher,
                            } for row in approvers}

# =============================================================================
def req_create_form_mods():
    """
        Function to be called from REST prep functions
         - main module & components (sites & events)
    """

    T = current.T
    db = current.db
    s3 = current.response.s3
    settings = current.deployment_settings

    table = db.req_req

    if not settings.get_req_inline_forms():
        # Amend the Save button
        default_type = table.type.default
        if default_type:
            req_submit_button = {1: T("Save and add Items"),
                                 3: T("Save and add People"),
                                 9: T("Save"),
                                 }
            s3.crud.submit_button = req_submit_button[default_type]

    # Hide fields which don't make sense in a Create form
    table.req_ref.readable = False
    table.commit_status.readable = table.commit_status.writable = False
    table.transit_status.readable = table.transit_status.writable = False
    table.fulfil_status.readable = table.fulfil_status.writable = False
    table.workflow_status.readable = table.workflow_status.writable = False
    table.cancel.readable = table.cancel.writable = False
    table.closed.readable = table.closed.writable = False
    table.date_recv.readable = table.date_recv.writable = False
    table.recv_by_id.readable = table.recv_by_id.writable = False

    if settings.get_req_requester_from_site():
        # Filter the list of Contacts to those for the site
        table.requester_id.widget = None
        table.requester_id.comment = PopupLink(c = "pr",
                                               f = "person",
                                               vars = {"child": "requester_id",
                                                       "parent": "req",
                                                       },
                                               title = s3.crud_strings["pr_person"].label_create,
                                               )
        s3.jquery_ready.append('''
$.filterOptionsS3({
'trigger':'site_id',
'target':'requester_id',
'lookupResource':'staff',
'lookupURL':S3.Ap.concat('/hrm/staff_for_site/'),
'msgNoRecords':'%s',
'optional':true,
})''' % T("No contacts yet defined for this site"))
        #table.site_id.comment = A(T("Set as default Site"),
        #                          _id="req_req_site_id_link",
        #                          _target="_blank",
        #                          _href=URL(c="default",
        #                                    f="user",
        #                                    args=["profile"]))

    req_types = settings.get_req_req_type()
    if "People" in req_types:
        # Show the Required Until Field
        # (gets turned-off by JS for other types)
        table.date_required_until.writable = True

    request = current.request
    if "type" not in request.get_vars:
        # Script to inject into Pages which include Request create forms
        req_helptext = '''
i18n.req_purpose="%s"
i18n.req_site_id="%s"
i18n.req_request_for_id="%s"
i18n.req_recv_by_id="%s"
i18n.req_items_purpose="%s"
i18n.req_items_site_id="%s"
i18n.req_items_recv_by_id="%s"
i18n.req_people_purpose="%s"
i18n.req_people_site_id="%s"
i18n.req_people_recv_by_id="%s"
i18n.req_next_msg="%s"
i18n.req_other_msg="%s"
i18n.req_details_mandatory="%s"''' % (table.purpose.label,
                                  table.site_id.label,
                                  table.request_for_id.label,
                                  table.recv_by_id.label,
                                  T("What the Items will be used for"),
                                  T("Deliver To"),
                                  T("Delivered To"),
                                  T("Task Details"),
                                  T("Report To"),
                                  T("Reported To"),
                                  T("Please enter the details on the next screen."),
                                  T("Please enter request details here."),
                                  T("Details field is required!"))
        s3.js_global.append(req_helptext)
        s3.scripts.append("/%s/static/scripts/S3/s3.req_create_variable.js" % request.application)

    else:
        s3.scripts.append("/%s/static/scripts/S3/s3.req_create.js" % request.application)

# =============================================================================
def req_hide_quantities(table):
    """
        Hide per-status quantity fields in Request create-forms

        Args:
            table: the Table (req_item or req_skill)
    """

    if not current.deployment_settings.get_req_item_quantities_writable():
        table.quantity_commit.readable = \
        table.quantity_commit.writable = False
        table.quantity_transit.readable = \
        table.quantity_transit.writable = False
        table.quantity_fulfil.readable = \
        table.quantity_fulfil.writable = False

# =============================================================================
def req_inline_form(req_type, method):
    """
        Function to be called from REST prep functions
            - to add req_item & req_skill components as inline forms

        Args:
            req_type: the request type (1=items, 3=skills)
            method: the URL request method
    """

    T = current.T
    s3db = current.s3db
    table = s3db.req_req
    s3 = current.response.s3
    postprocess = s3.req_req_postprocess

    if req_type == 1:

        # Custom Form
        settings = current.deployment_settings
        fields = [#req_ref
                  "site_id",
                  #is_template
                  "requester_id",
                  "date",
                  "priority",
                  "date_required",
                  InlineComponent(
                    "req_item",
                    label = T("Items"),
                    fields = ["item_id",
                              "item_pack_id",
                              "quantity",
                              "comments"
                              ]
                  ),
                  #purpose
                  "comments",
                  ]

        if method in ("create", "update"):
            # Dropdown not Autocomplete
            itable = s3db.req_req_item
            itable.item_id.widget = None

            # Options-filter item=>pack
            jquery_ready = s3.jquery_ready
            jquery_ready.append('''
$.filterOptionsS3({
'trigger':{'alias':'req_item','name':'item_id'},
'target':{'alias':'req_item','name':'item_pack_id'},
'scope':'row',
'lookupPrefix':'supply',
'lookupResource':'item_pack',
'msgNoRecords':i18n.no_packs,
'fncPrep':S3.supply.fncPrepItem,
'fncRepresent':S3.supply.fncRepresentItem
})''')
            if settings.get_req_requester_from_site():
                # Filter the list of Contacts to those for the site
                jquery_ready.append('''
$.filterOptionsS3({
'trigger':'site_id',
'target':'requester_id',
'lookupResource':'staff',
'lookupURL':S3.Ap.concat('/hrm/staff_for_site/'),
'msgNoRecords':'%s',
'optional':true,
})''' % T("No contacts yet defined for this site"))

                # Popup link to allow adding a contact (...for the site)
                table.requester_id.widget = None
                table.requester_id.comment = PopupLink(c = "pr",
                                                       f = "person",
                                                       vars = {"child": "requester_id",
                                                               "parent": "req",
                                                               },
                                                       title = s3.crud_strings["pr_person"].label_create,
                                                       )

                # Link to user profile to allow setting this site
                # as their current default site, so that they appear
                # in the dropdown themselves
                table.site_id.comment = A(T("Set as default Site"),
                                          _id = "req_req_site_id_link",
                                          _target = "_blank",
                                          _href = URL(c = "default",
                                                      f = "user",
                                                      args = ["profile"],
                                                      ),
                                          )

        if method in ("update", "read"):
            # Append status details
            status_fields = []
            if settings.get_req_status_writable():
                if settings.get_req_use_commit():
                    status_fields.append("commit_status")
                if settings.get_req_show_quantity_transit():
                    status_fields.append("transit_status")
                status_fields.append("fulfil_status")
            status_fields.append("date_recv")

            fields.extend(status_fields)

            # Show request number?
            if settings.get_req_use_req_number():
                if settings.get_req_generate_req_number():
                    table.req_ref.writable = False
                fields.insert(0, "req_ref")
        else:
            # Is-template flag can only be set during create
            fields.insert(1, "is_template")

        if settings.get_req_items_ask_purpose():
            fields.insert(-1, "purpose")

        if postprocess:
            crud_form = CustomForm(*fields, postprocess=postprocess)
        else:
            crud_form = CustomForm(*fields)
        s3db.configure("req_req",
                       crud_form = crud_form,
                       )

    elif req_type == 3:
        # Custom Form
        stable = s3db.req_req_skill
        stable.skill_id.label = T("Required Skills (optional)")
        # Custom Form
        settings = current.deployment_settings
        fields = ["site_id",
                  "requester_id",
                  "date",
                  "priority",
                  "date_required",
                  "date_required_until",
                  "purpose",
                  InlineComponent(
                    "req_skill",
                    label = T("Skills"),
                    fields = ["quantity",
                              "skill_id",
                              "comments"
                              ]
                  ),
                  "comments",
                  ]
        if method == "update":
            if settings.get_req_status_writable():
                fields.insert(8, "fulfil_status")
                if settings.get_req_show_quantity_transit():
                    fields.insert(8, "transit_status")
                if settings.get_req_use_commit():
                    fields.insert(8, "commit_status")
            fields.insert(8, "date_recv")

            if settings.get_req_requester_from_site():
                # Filter the list of Contacts to those for the site
                table.requester_id.widget = None
                table.requester_id.comment = PopupLink(c = "pr",
                                                       f = "person",
                                                       vars = {"child": "requester_id",
                                                               "parent": "req",
                                                               },
                                                       title = s3.crud_strings["pr_person"].label_create,
                                                       )
                s3.jquery_ready.append('''
$.filterOptionsS3({
'trigger':'site_id',
'target':'requester_id',
'lookupResource':'staff',
'lookupURL':S3.Ap.concat('/hrm/staff_for_site/'),
'msgNoRecords':'%s',
'optional':true,
})''' % T("No contacts yet defined for this site"))
                table.site_id.comment = A(T("Set as default Site"),
                                          _id = "req_req_site_id_link",
                                          _target = "_blank",
                                          _href = URL(c="default",
                                                      f="user",
                                                      args = ["profile"],
                                                      ),
                                          )

        else:
            fields.insert(1, "is_template")
        if settings.get_req_use_req_number() and \
           not settings.get_req_generate_req_number():
            fields.insert(0, "req_ref")
        if postprocess:
            crud_form = CustomForm(*fields, postprocess=postprocess)
        else:
            crud_form = CustomForm(*fields)
        s3db.configure("req_req",
                       crud_form = crud_form,
                       )

    # Reset to standard submit button
    s3.crud.submit_button = T("Save")

# END =========================================================================
