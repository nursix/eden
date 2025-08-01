"""
    DVR Beneficiary Registry and Case Management
"""

module = request.controller
resourcename = request.function

if not settings.has_module(module):
    raise HTTP(404, body="Module disabled: %s" % module)

# -----------------------------------------------------------------------------
def index():
    """ Module's Home Page """

    return settings.customise_home(module, alt_function="index_alt")

# -----------------------------------------------------------------------------
def index_alt():
    """
        Default module homepage
    """

    # Just redirect to the person list
    s3_redirect_default(URL(f="person"))

# =============================================================================
# Beneficiaries
#
def person():
    """ Persons: CRUD Controller """

    def prep(r):

        # Filter to persons who have a case registered
        resource = r.resource
        resource.add_filter(FS("dvr_case.id") != None)

        get_vars = r.get_vars
        mine = True if get_vars.get("mine") == "1" else False

        beneficiary = settings.get_dvr_label() # If we add more options in future then == "Beneficiary"
        if beneficiary:
            CASES = T("Beneficiaries")
            CURRENT = T("Current Beneficiaries")
            CLOSED = T("Former Beneficiaries")
        else:
            if mine:
                CASES = T("My Cases")
                CURRENT = T("My Current Cases")
            else:
                CASES = T("Cases")
                CURRENT = T("Current Cases")
            CLOSED = T("Closed Cases")

        # Filters to split case list
        if not r.record:

            # Set the case default status
            default_status = s3db.dvr_case_default_status()

            # Filter to active/archived cases
            archived = get_vars.get("archived")
            if archived == "1":
                archived = True
                CASES = T("Archived Cases")
                query = FS("dvr_case.archived") == True
            else:
                archived = False
                query = (FS("dvr_case.archived") == False) | \
                        (FS("dvr_case.archived") == None)

            # Filter for cases assigned to the logged-in user
            if mine:
                human_resource_id = auth.s3_logged_in_human_resource()
                if human_resource_id:
                    query &= (FS("dvr_case.human_resource_id") == human_resource_id)
                else:
                    query &= (FS("dvr_case.human_resource_id").belongs(set()))

            # Filter to open/closed cases
            # (also filtering status filter opts)
            closed = get_vars.get("closed")
            get_status_opts = s3db.dvr_case_status_filter_opts
            if closed == "only":
                # Show only closed cases
                CASES = CLOSED
                query &= FS("dvr_case.status_id$is_closed") == True
                status_opts = lambda: get_status_opts(closed=True)
                default_status = None
            elif closed == "1" or closed == "include":
                # Show both closed and open cases
                status_opts = get_status_opts
                default_status = None
            else:
                # show only open cases (default)
                CASES = CURRENT
                query &= (FS("dvr_case.status_id$is_closed") == False) | \
                         (FS("dvr_case.status_id$is_closed") == None)
                status_opts = lambda: get_status_opts(closed=False)

            resource.add_filter(query)
        else:
            archived = False
            status_opts = s3db.dvr_case_status_filter_opts
            default_status = None

        # Should not be able to delete records in this view
        resource.configure(deletable = False)

        if r.component and r.id:
            ctable = r.component.table
            if "case_id" in ctable.fields and \
               str(ctable.case_id.type)[:18] == "reference dvr_case":

                # Find the Case ID
                dvr_case = s3db.dvr_case
                query = (dvr_case.person_id == r.id) & \
                        (dvr_case.deleted != True)
                cases = db(query).select(dvr_case.id, limitby=(0, 2))

                case_id = ctable.case_id
                if cases:
                    # Set default
                    case_id.default = cases.first().id
                if len(cases) == 1:
                    # Only one case => hide case selector
                    case_id.readable = case_id.writable = False
                else:
                    # Configure case selector
                    case_id.requires = IS_ONE_OF(db(query), "dvr_case.id",
                                                 case_id.represent,
                                                 )

        if r.interactive:

            # Adapt CRUD strings to context
            if beneficiary:
                s3.crud_strings["pr_person"] = Storage(
                    label_create = T("Create Beneficiary"),
                    title_display = T("Beneficiary Details"),
                    title_list = CASES,
                    title_update = T("Edit Beneficiary Details"),
                    label_list_button = T("List Beneficiaries"),
                    label_delete_button = T("Delete Beneficiary"),
                    msg_record_created = T("Beneficiary added"),
                    msg_record_modified = T("Beneficiary details updated"),
                    msg_record_deleted = T("Beneficiary deleted"),
                    msg_list_empty = T("No Beneficiaries currently registered")
                    )
            else:
                s3.crud_strings["pr_person"] = Storage(
                    label_create = T("Create Case"),
                    title_display = T("Case Details"),
                    title_list = CASES,
                    title_update = T("Edit Case Details"),
                    label_list_button = T("List Cases"),
                    label_delete_button = T("Delete Case"),
                    msg_record_created = T("Case added"),
                    msg_record_modified = T("Case details updated"),
                    msg_record_deleted = T("Case deleted"),
                    msg_list_empty = T("No Cases currently registered")
                    )

            component = r.component
            if not component:

                from core import CustomForm, \
                                 InlineComponent, \
                                 TextFilter, \
                                 OptionsFilter, \
                                 get_filter_options

                # Expose the "archived"-flag? (update forms only)
                if r.record and r.method != "read":
                    ctable = s3db.dvr_case
                    field = ctable.archived
                    field.readable = field.writable = True

                # Module-specific CRUD form
                # NB: this assumes single case per person, must use
                #     case perspective (dvr/case) for multiple cases
                #     per person!
                crud_form = CustomForm(
                                "dvr_case.organisation_id",
                                "dvr_case.date",
                                "dvr_case.status_id",
                                "pe_label",
                                #"dvr_case.reference",
                                "first_name",
                                "middle_name",
                                "last_name",
                                "date_of_birth",
                                "gender",
                                InlineComponent(
                                        "contact",
                                        fields = [("", "value")],
                                        filterby = {"field": "contact_method",
                                                    "options": "EMAIL",
                                                    },
                                        label = T("Email"),
                                        multiple = False,
                                        name = "email",
                                        ),
                                InlineComponent(
                                        "contact",
                                        fields = [("", "value")],
                                        filterby = {"field": "contact_method",
                                                    "options": "SMS",
                                                    },
                                        label = T("Mobile Phone"),
                                        multiple = False,
                                        name = "phone",
                                        ),
                                "person_details.nationality",
                                InlineComponent(
                                        "address",
                                        label = T("Current Address"),
                                        fields = [("", "location_id")],
                                        filterby = {"field": "type",
                                                    "options": "1",
                                                    },
                                        link = False,
                                        multiple = False,
                                        ),
                                "dvr_case.comments",
                                "dvr_case.archived",
                                )

                # Module-specific filter widgets
                filter_widgets = [
                    TextFilter(["pe_label",
                                "first_name",
                                "middle_name",
                                "last_name",
                                #"email.value",
                                #"phone.value",
                                #"dvr_case.reference",
                                ],
                                label = T("Search"),
                                comment = T("You can search by name, ID or case number"),
                                ),
                    OptionsFilter("dvr_case.status_id",
                                  cols = 3,
                                  default = default_status,
                                  #label = T("Case Status"),
                                  options = status_opts,
                                  sort = False,
                                  ),
                    OptionsFilter("person_details.nationality",
                                  ),
                    ]

                # Add filter for case flags
                if settings.get_dvr_case_flags():
                    filter_widgets.append(
                        OptionsFilter("case_flag_case.flag_id",
                                      label = T("Flags"),
                                      options = get_filter_options("dvr_case_flag",
                                                                   translate = True,
                                                                   ),
                                      cols = 3,
                                      hidden = True,
                                      ))

                # Add filter for transferability if relevant for deployment
                if settings.get_dvr_manage_transferability():
                    filter_widgets.append(
                        OptionsFilter("dvr_case.transferable",
                                      options = {True: T("Yes"),
                                                 False: T("No"),
                                                 },
                                      cols = 2,
                                      hidden = True,
                                      ))

                resource.configure(crud_form = crud_form,
                                   filter_widgets = filter_widgets,
                                   )

            elif component.tablename == "dvr_case_activity":

                person_id = r.record.id
                organisation_id = s3db.dvr_case_organisation(person_id)

                # Set default status
                s3db.dvr_case_activity_default_status()

                if settings.get_dvr_vulnerabilities():
                    # Limit selectable vulnerabilities to case
                    s3db.dvr_configure_case_vulnerabilities(person_id)

                if settings.get_dvr_manage_response_actions():

                    # Set defaults for inline responses
                    s3db.dvr_set_response_action_defaults()

                    # Limit selectable response themes to case organisation
                    if settings.get_dvr_response_themes():
                        s3db.dvr_configure_case_responses(organisation_id)

                # Configure CRUD form
                component.configure(crud_form=s3db.dvr_case_activity_form(r))


            elif component.tablename == "dvr_response_action":

                person_id = r.record.id
                organisation_id = s3db.dvr_case_organisation(person_id)

                # Set defaults
                s3db.dvr_set_response_action_defaults()

                if settings.get_dvr_vulnerabilities():
                    # Limit selectable vulnerabilities to case
                    s3db.dvr_configure_case_vulnerabilities(person_id)

                # Limit selectable response themes to case organisation
                if settings.get_dvr_response_themes():
                    s3db.dvr_configure_case_responses(organisation_id)

            elif component.tablename == "dvr_vulnerability":

                person_id = r.record.id
                organisation_id = s3db.dvr_case_organisation(person_id)

                # Limit vulnerabilities by case organisation sectors
                s3db.dvr_configure_vulnerability_types(organisation_id)

                # Set default human_resource_id
                field = component.table.human_resource_id
                field.default = current.auth.s3_logged_in_human_resource()

            elif r.component_name == "allowance" and \
                 r.method in (None, "update"):

                records = component.select(["status"], as_rows=True)
                if len(records) == 1:
                    record = records[0]
                    table = component.table
                    readonly = []
                    if record.status == 2:
                        # Can't change payment details if already paid
                        readonly = ["person_id",
                                    "entitlement_period",
                                    "date",
                                    "paid_on",
                                    "amount",
                                    "currency",
                                    ]
                    for fn in readonly:
                        if fn in table.fields:
                            field = table[fn]
                            field.writable = False
                            field.comment = None

            elif r.component_name == "case_task":

                s3db.dvr_configure_case_tasks(r)

        # Module-specific list fields (must be outside of r.interactive)
        list_fields = [#"dvr_case.reference",
                       #"pe_label",
                       "first_name",
                       "middle_name",
                       "last_name",
                       "date_of_birth",
                       "gender",
                       "dvr_case.date",
                       "dvr_case.status_id",
                       ]
        resource.configure(list_fields = list_fields,
                           )

        return True
    s3.prep = prep

    return crud_controller("pr", "person", rheader=s3db.dvr_rheader)

# -----------------------------------------------------------------------------
def person_search():
    """
        Controller for autocomplete-searches
    """

    def prep(r):

        if r.method != "search_ac":
            return False

        # Filter to persons who have a case registered
        resource = r.resource
        resource.add_filter(FS("dvr_case.id") != None)
        return True

    s3.prep = prep

    return crud_controller("pr", "person")

# -----------------------------------------------------------------------------
def document():

    def prep(r):

        table = r.table
        resource = r.resource

        viewing = r.viewing
        if viewing:
            vtablename, record_id = viewing
        else:
            return False

        ctable = s3db.dvr_case
        auth = current.auth
        has_permission = auth.s3_has_permission
        accessible_query = auth.s3_accessible_query

        if vtablename == "pr_person":
            if not has_permission("read", "pr_person", record_id):
                r.unauthorised()
            include_activity_docs = settings.get_dvr_case_include_activity_docs()
            include_group_docs = settings.get_dvr_case_include_group_docs()
            query = accessible_query("read", ctable) & \
                    (ctable.person_id == record_id) & \
                    (ctable.deleted == False)

        elif vtablename == "dvr_case":
            include_activity_docs = False
            include_group_docs = False
            query = accessible_query("read", ctable) & \
                    (ctable.id == record_id) & \
                    (ctable.deleted == False)
        else:
            # Unsupported
            return False

        # Get the case doc_id
        case = db(query).select(ctable.doc_id,
                                ctable.organisation_id,
                                limitby = (0, 1),
                                orderby = ~ctable.modified_on,
                                ).first()
        if case:
            doc_ids = [case.doc_id] if case.doc_id else []
        else:
            # No case found
            r.error(404, "Case not found")

        # Set default organisation_id to case org
        table.organisation_id.default = case.organisation_id

        # Include case groups
        if include_group_docs:

            # Look up relevant case groups
            mtable = s3db.pr_group_membership
            gtable = s3db.pr_group
            join = gtable.on((gtable.id == mtable.group_id) & \
                             (gtable.group_type == 7))
            query = accessible_query("read", mtable) & \
                    (mtable.person_id == record_id) & \
                    (mtable.deleted == False)
            rows = db(query).select(gtable.doc_id,
                                    join = join,
                                    orderby = ~mtable.created_on,
                                    )

            # Append the doc_ids
            for row in rows:
                if row.doc_id:
                    doc_ids.append(row.doc_id)

        # Include case activities
        if include_activity_docs:

            # Look up relevant case activities
            atable = s3db.dvr_case_activity
            query = accessible_query("read", atable) & \
                    (atable.person_id == record_id) & \
                    (atable.deleted == False)
            rows = db(query).select(atable.doc_id,
                                    orderby = ~atable.created_on,
                                    )

            # Append the doc_ids
            for row in rows:
                if row.doc_id:
                    doc_ids.append(row.doc_id)

        field = r.table.doc_id
        if include_activity_docs or include_group_docs:

            # Make doc_id readable and visible in table
            field.represent = s3db.dvr_DocEntityRepresent()
            field.label = T("Attachment of")
            field.readable = True
            s3db.configure("doc_document",
                           list_fields = ["id",
                                          (T("Attachment of"), "doc_id"),
                                          "name",
                                          "file",
                                          "date",
                                          "comments",
                                          ],
                           )

        # Apply filter and defaults
        if len(doc_ids) == 1:
            # Single doc_id => set default, hide field
            doc_id = doc_ids[0]
            field.default = doc_id
            r.resource.add_filter(FS("doc_id") == doc_id)
        else:
            # Multiple doc_ids => default to case, make selectable
            field.default = doc_ids[0]
            field.readable = field.writable = True
            field.requires = IS_ONE_OF(db, "doc_entity.doc_id",
                                       field.represent,
                                       filterby = "doc_id",
                                       filter_opts = doc_ids,
                                       orderby = "instance_type",
                                       sort = False,
                                       )
            r.resource.add_filter(FS("doc_id").belongs(doc_ids))

        return True
    s3.prep = prep

    return crud_controller("doc", "document",
                           rheader = s3db.dvr_rheader,
                           )

# -----------------------------------------------------------------------------
def group_membership():
    """
        CRUD Controller for person<=>group links, normally called
        only from component tab in person perspective (e.g. family members)
    """

    def prep(r):

        table = r.table
        resource = r.resource

        get_vars = r.get_vars
        if "viewing" in get_vars:

            try:
                vtablename, record_id = get_vars["viewing"].split(".")
            except ValueError:
                return False

            if vtablename == "pr_person":
                # Get all group_ids with this person_id
                gtable = s3db.pr_group
                join = gtable.on(gtable.id == table.group_id)
                query = (table.person_id == record_id) & \
                        (gtable.group_type == 7) & \
                        (table.deleted != True)
                rows = db(query).select(table.group_id,
                                        join=join,
                                        )
                group_ids = set(row.group_id for row in rows)
                # Hide the link for this person (to prevent changes/deletion)
                if group_ids:
                    # Single group ID?
                    group_id = tuple(group_ids)[0] if len(group_ids) == 1 else None
                elif r.http == "POST":
                    name = s3_fullname(record_id)
                    group_id = gtable.insert(name = name,
                                             group_type = 7,
                                             )
                    s3db.update_super(gtable, {"id": group_id})
                    table.insert(group_id = group_id,
                                 person_id = record_id,
                                 group_head = True,
                                 )
                    group_ids = {group_id}
                resource.add_filter(FS("person_id") != record_id)
            else:
                group_ids = set()


            # Show only links for relevant cases
            # NB Filter also prevents showing all links if case_ids is empty
            if not r.id:
                if len(group_ids) == 1:
                    r.resource.add_filter(FS("group_id") == group_id)
                else:
                    r.resource.add_filter(FS("group_id").belongs(group_ids))

            list_fields = ["person_id",
                           "person_id$gender",
                           "person_id$date_of_birth",
                           ]

            if len(group_ids) == 0:
                # No case group exists, will be auto-generated on POST,
                # hide the field in the form:
                field = table.group_id
                field.readable = field.writable = False
            elif len(group_ids) == 1:
                field = table.group_id
                field.default = group_id
                # If we have only one relevant case, then hide the group ID:
                field.readable = field.writable = False
            elif len(group_ids) > 1:
                # Show the case ID in list fields if there is more than one
                # relevant case
                list_fields.insert(0, "group_id")
            r.resource.configure(list_fields = list_fields)

        # Do not allow update of person_id
        if r.id:
            field = table.person_id
            field.writable = False
            field.comment = None

        return True
    s3.prep = prep

    # Disable unwanted fields in person widget (can override in template)
    settings.pr.request_email = False
    settings.pr.request_home_phone = False
    settings.hrm.email_required = False

    return crud_controller("pr", "group_membership",
                           rheader = s3db.dvr_rheader,
                           )

# =============================================================================
# Cases
#
def case():
    """ Cases: CRUD Controller """

    s3db.dvr_case_default_status()

    return crud_controller(rheader=s3db.dvr_rheader)

# -----------------------------------------------------------------------------
def case_flag():
    """ Case Flags: CRUD Controller """

    def prep(r):
        if settings.get_dvr_case_event_types_org_specific():
            s3db.org_restrict_for_organisations(r.resource)

        return True
    s3.prep = prep

    return crud_controller()

# -----------------------------------------------------------------------------
def case_status():
    """ Case Statuses: CRUD Controller """

    return crud_controller()

# =============================================================================
# Case Activities
#
def case_activity():
    """ Case Activities: CRUD Controller """

    def prep(r):

        resource = r.resource

        # Set default statuses
        s3db.dvr_case_activity_default_status()

        # Set defaults for inline responses
        if settings.get_dvr_manage_response_actions():
            s3db.dvr_set_response_action_defaults()

        # Configure form
        resource.configure(crud_form=s3db.dvr_case_activity_form(r))

        # Set default person_id when creating from popup
        if r.method == "create" and \
           r.representation == "popup" and "person_id" not in r.post_vars:
            person_id = r.get_vars.get("~.person_id")
            if person_id:
                field = resource.table.person_id
                try:
                    field.default = int(person_id)
                except (TypeError, ValueError):
                    pass
                else:
                    field.writable = False

        if not r.record:

            # Filter out case activities of archived cases
            query = (FS("person_id$dvr_case.archived") == False)
            resource.add_filter(query)

            # Filter out case activities of closed cases
            query = (FS("person_id$dvr_case.status_id$is_closed") == False)
            resource.add_filter(query)

            # Mine-filter
            mine = r.get_vars.get("mine")
            if mine == "1":

                # Adapt CRUD-strings to perspective
                s3.crud_strings["dvr_case_activity"]["title_list"] = T("My Activities")

                # Filter for case activities assigned to the current user
                human_resource_id = auth.s3_logged_in_human_resource()
                if human_resource_id:
                    query = (FS("human_resource_id") == human_resource_id)
                else:
                    query = (FS("human_resource_id").belongs(set()))
                resource.add_filter(query)

        # Prepend person data to default list fields
        list_fields = ["person_id$pe_label",
                       "person_id$first_name",
                       "person_id$last_name",
                       ] + resource.get_config("list_fields", [])

        resource.configure(list_fields = list_fields,
                           insertable = False,
                           deletable = False,
                           )
        return True
    s3.prep = prep

    return crud_controller()

# -----------------------------------------------------------------------------
def due_followups():
    """ Case Activities to follow up: CRUD Controller """

    def prep(r):

        resource = r.resource

        # Set default statuses
        s3db.dvr_case_activity_default_status()

        # Set defaults for inline responses
        if settings.get_dvr_manage_response_actions():
            s3db.dvr_set_response_action_defaults()

        # Configure form
        resource.configure(crud_form=s3db.dvr_case_activity_form(r))

        # Adapt CRUD strings to perspective
        s3.crud_strings["dvr_case_activity"]["title_list"] = T("Activities to follow up")

        if not r.record:
            # Filters for due followups
            query = (FS("followup") == True) & \
                    (FS("followup_date") <= datetime.datetime.utcnow().date()) & \
                    (FS("status_id$is_closed") == False) & \
                    ((FS("person_id$dvr_case.archived") == None) | \
                    (FS("person_id$dvr_case.archived") == False))
            resource.add_filter(query)

            # Filter out case activities of archived cases
            query = (FS("person_id$dvr_case.archived") == False)
            resource.add_filter(query)

            # Filter out case activities of closed cases
            query = (FS("person_id$dvr_case.status_id$is_closed") == False)
            resource.add_filter(query)

            # Mine-filter
            mine = r.get_vars.get("mine")
            if mine == "1":

                # Adapt CRUD-strings to perspective
                s3.crud_strings["dvr_case_activity"]["title_list"] = T("My Activities to follow-up")

                # Filter for case activities assigned to the current user
                human_resource_id = auth.s3_logged_in_human_resource()
                if human_resource_id:
                    query = (FS("human_resource_id") == human_resource_id)
                else:
                    query = (FS("human_resource_id").belongs(set()))
                resource.add_filter(query)

        list_fields = ["case_id$reference",
                       "person_id$first_name",
                       "person_id$last_name",
                       ] + resource.get_config("list_fields", [])

        resource.configure(list_fields = list_fields,
                           insertable = False,
                           deletable = False,
                           )
        return True
    s3.prep = prep

    return crud_controller("dvr", "case_activity")

# -----------------------------------------------------------------------------
def provider_type():
    """ Provider Types for Case Activities: CRUD Controller """

    return crud_controller()

# -----------------------------------------------------------------------------
def referral_type():
    """ Referral Types: CRUD Controller """

    return crud_controller()

# =============================================================================
# Responses
#
def response_theme():
    """ Response Themes: CRUD Controller """

    return crud_controller()

# -----------------------------------------------------------------------------
def response_type():
    """ Response Types: CRUD Controller """

    def prep(r):
        field = r.table.parent
        field.requires = IS_EMPTY_OR(IS_ONE_OF(db, "%s.id" % r.tablename,
                                               field.represent,
                                               ))
        return True
    s3.prep = prep

    return crud_controller()

# -----------------------------------------------------------------------------
def response_status():
    """ Response Statuses: CRUD Controller """

    return crud_controller()

# -----------------------------------------------------------------------------
def response_action():
    """ Response Actions: CRUD Controller """

    def prep(r):

        resource = r.resource
        table = resource.table
        record = r.record

        # Beneficiary is required and must have a case file
        ptable = s3db.pr_person
        ctable = s3db.dvr_case
        dbset = db((ptable.id == ctable.person_id) & \
                   (ctable.archived == False) & \
                   (ctable.deleted == False))
        field = table.person_id
        field.requires = IS_ONE_OF(dbset, "pr_person.id",
                                   field.represent,
                                   )

        # Set defaults
        s3db.dvr_set_response_action_defaults()

        # Create/delete requires context perspective
        insertable = deletable = False

        person_id = None

        viewing = r.viewing
        if viewing:
            vtablename, person_id = viewing
            if vtablename != "pr_person":
                # Not supported
                return None

            # Must be permitted to read the person record
            if not auth.s3_has_permission("read", "pr_person", person_id):
                r.unauthorised()

            # Filter to case viewed
            resource.add_filter(FS("person_id") == person_id)

            # Enable case activity selection
            field = table.case_activity_id
            field.readable = field.writable = True

            # Restrict case activity selection to the case viewed
            atable = s3db.dvr_case_activity
            field.requires = IS_ONE_OF(db(atable.person_id == person_id),
                                       "dvr_case_activity.id",
                                       field.represent,
                                       )

            # Can create and delete records in this perspective
            insertable = deletable = True

        elif record:
            person_id = record.person_id

        else:
            # Filter out response actions of archived cases
            query = (FS("person_id$dvr_case.archived") == False)
            resource.add_filter(query)

        if person_id and settings.get_dvr_vulnerabilities():
            # Limit selectable vulnerabilities to case
            s3db.dvr_configure_case_vulnerabilities(person_id)

        # Filter for "mine"
        mine = r.get_vars.get("mine")
        if mine == "a":
            # Filter for response actions assigned to logged-in user
            mine_selector = FS("human_resource_id")
            title_list = T("Actions assigned to me")
        elif mine == "r":
            # Filter for response actions managed by logged-in user
            mine_selector = FS("case_activity_id$human_resource_id")
            title_list = T("Actions managed by me")
        else:
            mine_selector = None

        if mine_selector:
            human_resource_id = auth.s3_logged_in_human_resource()
            if human_resource_id:
                resource.add_filter(mine_selector == human_resource_id)
            else:
                # Show nothing for mine if user is not a HR
                resource.add_filter(mine_selector.belongs(set()))
            s3.crud_strings[resource.tablename]["title_list"] = title_list

        resource.configure(insertable = insertable,
                           deletable = deletable,
                           )

        return True
    s3.prep = prep

    return crud_controller(rheader=s3db.dvr_rheader)

# -----------------------------------------------------------------------------
def termination_type():
    """ Termination Types: CRUD Controller """

    def prep(r):

        if settings.get_dvr_case_activity_use_service_type() and \
           settings.get_org_services_hierarchical():

            # Limit the selection to root services (case activity
            # threads are usually per root service type, and all
            # sub-categories should use a common exit type taxonomy)
            field = r.table.service_id
            query = (db.org_service.parent == None)
            field.requires = IS_EMPTY_OR(IS_ONE_OF(db(query),
                                                   "org_service.id",
                                                   field.represent,
                                                   ))
        return True
    s3.prep = prep

    return crud_controller()

# -----------------------------------------------------------------------------
def case_activity_update_type():
    """ Case Activity Update Types: CRUD Controller """

    return crud_controller()

# -----------------------------------------------------------------------------
def case_activity_status():
    """ Case Activity Statuses: CRUD Controller """

    return crud_controller()

# =============================================================================
# Allowance
#
def allowance():
    """ Allowances: CRUD Controller """

    deduplicate = s3db.get_config("pr_person", "deduplicate")

    def person_deduplicate(item):
        """
            Wrapper for person deduplicator to identify person
            records, but preventing actual imports of persons
        """

        # Run standard person deduplication
        if deduplicate:
            deduplicate(item)

        # Person not found?
        if item.method != item.METHOD.UPDATE:

            # Provide some meaningful details of the failing
            # person record to facilitate correction of the source:
            from core import s3_str
            person_details = []
            append = person_details.append
            data = item.data
            for f in ("pe_label", "last_name", "first_name", "date_of_birth"):
                value = data.get(f)
                if value:
                    append(s3_str(value))
            error = "Person not found: %s" % ", ".join(person_details)
            item.error = error
            item.element.set(current.xml.ATTRIBUTE["error"], error)

            # Reject any new person records
            item.accepted = False

        # Skip - we don't want to update person records here
        item.skip = True
        item.method = None

    s3db.configure("pr_person", deduplicate=person_deduplicate)

    def prep(r):

        if r.method == "import":
            # Allow deduplication of persons by pe_label: existing
            # pe_labels would be caught by IS_NOT_ONE_OF before
            # reaching the deduplicator, so remove the validator here:
            ptable = s3db.pr_person
            ptable.pe_label.requires = None

        record = r.record
        if record:
            table = r.table
            if record.status == 2:
                # Can't change payment details if already paid
                readonly = ["person_id",
                            "entitlement_period",
                            "date",
                            "paid_on",
                            "amount",
                            "currency",
                            ]
                for fn in readonly:
                    if fn in table.fields:
                        field = table[fn]
                        field.writable = False
                        field.comment = None
        return True
    s3.prep = prep

    table = s3db.dvr_allowance

    return crud_controller(csv_extra_fields = [{"label": "Date",
                                                "field": table.date,
                                                },
                                               ],
                           )

# =============================================================================
# Grants
#
def grant_type():
    """ Beneficiary Grant Types: CRUD Controller """

    return crud_controller(rheader=s3db.dvr_rheader)

def grant():
    """ Beneficiary Grants: CRUD Controller """

    return crud_controller()

# =============================================================================
# Appointments
#
def case_appointment():
    """ Appointments: CRUD Controller """

    def prep(r):

        if r.method == "import":
            # Allow deduplication of persons by pe_label: existing
            # pe_labels would be caught by IS_NOT_ONE_OF before
            # reaching the deduplicator, so remove the validator here:
            ptable = s3db.pr_person
            ptable.pe_label.requires = None

        else:
            mine = True if r.get_vars.get("mine") == "1" else False
            if mine:
                human_resource_id = auth.s3_logged_in_human_resource()
                if human_resource_id:
                    query = (FS("human_resource_id") == human_resource_id)
                else:
                    query = (FS("human_resource_id").belongs(set()))
                r.resource.add_filter(query)

        return True
    s3.prep = prep

    table = s3db.dvr_case_appointment

    return crud_controller(csv_extra_fields = [{"label": "Appointment Type",
                                                "field": table.type_id,
                                                },
                                               {"label": "Appointment Date",
                                                "field": table.date,
                                                },
                                               {"label": "Appointment Status",
                                                "field": table.status,
                                                },
                                               ],
                           )

# -----------------------------------------------------------------------------
def case_appointment_type():
    """ Appointment Type: CRUD Controller """

    def prep(r):
        if settings.get_dvr_case_event_types_org_specific():
            s3db.org_restrict_for_organisations(r.resource)

        return True
    s3.prep = prep

    return crud_controller()

# =============================================================================
# Case Events
#
def case_event():
    """ Case Event Types: CRUD Controller """

    def prep(r):
        if not r.component:
            list_fields = ["date",
                           (T("ID"), "person_id$pe_label"),
                           "person_id",
                           "type_id",
                           (T("Registered by"), "created_by"),
                           "comments",
                           ]
            r.resource.configure(list_fields = list_fields,
                                 )
        return True
    s3.prep = prep

    return crud_controller()

# -----------------------------------------------------------------------------
def case_event_type():
    """ Case Event Types: CRUD Controller """

    def prep(r):
        if settings.get_dvr_case_event_types_org_specific():
            s3db.org_restrict_for_organisations(r.resource)

        return True
    s3.prep = prep

    return crud_controller()

# =============================================================================
# Needs
#
def need():
    """ Needs: CRUD Controller """

    return crud_controller()

# =============================================================================
# Vulnerability
#
def vulnerability_type():
    """ Vulnerability Types: CRUD Controller """

    return crud_controller()

# =============================================================================
# Notes
#
def note():
    """ Notes: CRUD Controller """

    # Coming from a Profile page?"
    person_id = get_vars.get("~.person_id")
    if person_id:
        field = s3db.dvr_note.person_id
        field.default = person_id
        field.readable = field.writable = False

    return crud_controller()

def note_type():
    """ Note Types: CRUD Controller """

    return crud_controller()

# =============================================================================
# Case Tasks
#
def task():
    """ Case Tasks: CRUD Controller """

    settings.base.bigtable = True

    def prep(r):

        s3db.dvr_configure_case_tasks(r)

        resource = r.resource
        r.resource.configure(insertable = False,
                             deletable = False,
                             )
        return True
    s3.prep = prep

    return crud_controller(rheader=s3db.dvr_rheader)

# =============================================================================
# Residence Status
#
def residence_status_type():
    """ Residence Status Types: CRUD Controller """

    return crud_controller()

# -----------------------------------------------------------------------------
def residence_permit_type():
    """ Residence Permit Types: CRUD Controller """

    return crud_controller()

# =============================================================================
# Service Contacts
#
def service_contact_type():
    """ Service Contact Types: CRUD Controller """

    return crud_controller()

# END =========================================================================
