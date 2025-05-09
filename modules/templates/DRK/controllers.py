"""
    Custom controllers for DRK/Village

    License: MIT
"""

from gluon import current, redirect
from gluon.html import *
from gluon.storage import Storage

from core import CustomController

THEME = "DRK"

# =============================================================================
class index(CustomController):
    """ Custom Home Page """

    def __call__(self):

        output = {}

        T = current.T
        s3 = current.response.s3

        auth = current.auth
        settings = current.deployment_settings


        # Defaults
        login_form = None
        login_div = None
        announcements = None
        announcements_title = None

        roles = current.session.s3.roles
        sr = auth.get_system_roles()
        if sr.AUTHENTICATED in roles:
            # Logged-in user
            # => display announcements

            from core import S3DateTime
            dtrepr = lambda dt: S3DateTime.datetime_represent(dt, utc=True)

            filter_roles = roles if sr.ADMIN not in roles else None
            posts = self.get_announcements(roles=filter_roles)

            # Render announcements list
            announcements = UL(_class="announcements")
            if posts:
                announcements_title = T("Announcements")
                priority_classes = {2: "announcement-important",
                                    3: "announcement-critical",
                                    }
                priority_icons = {2: "fa-exclamation-circle",
                                  3: "fa-exclamation-triangle",
                                  }
                for post in posts:
                    # The header
                    header = H4(post.name)

                    # Priority
                    priority = post.priority
                    # Add icon to header?
                    icon_class = priority_icons.get(post.priority)
                    if icon_class:
                        header = TAG[""](I(_class="fa %s announcement-icon" % icon_class),
                                         header,
                                         )
                    # Priority class for the box
                    prio = priority_classes.get(priority, "")

                    row = LI(DIV(DIV(DIV(dtrepr(post.date),
                                        _class = "announcement-date",
                                        ),
                                    _class="fright",
                                    ),
                                 DIV(DIV(header,
                                         _class = "announcement-header",
                                         ),
                                     DIV(XML(post.body),
                                         _class = "announcement-body",
                                         ),
                                     _class="announcement-text",
                                    ),
                                 _class = "announcement-box %s" % prio,
                                 ),
                             )
                    announcements.append(row)
        else:
            # Anonymous user
            # => provide a login box
            login_div = DIV(H3(T("Login")),
                            )
            auth.messages.submit_button = T("Login")
            login_form = auth.login(inline=True)

        output = {"login_div": login_div,
                  "login_form": login_form,
                  "announcements": announcements,
                  "announcements_title": announcements_title,
                  }

        # Custom view and homepage styles
        self._view(settings.get_theme_layouts(), "index.html")

        return output

    # -------------------------------------------------------------------------
    @staticmethod
    def get_announcements(roles=None):
        """
            Get current announcements

            Args:
                roles: filter announcement by these roles

            Returns:
                any announcements (Rows)
        """

        db = current.db
        s3db = current.s3db

        # Look up all announcements
        ptable = s3db.cms_post
        stable = s3db.cms_series
        join = stable.on((stable.id == ptable.series_id) & \
                         (stable.name == "Announcements") & \
                         (stable.deleted == False))
        query = (ptable.date <= current.request.utcnow) & \
                (ptable.expired == False) & \
                (ptable.deleted == False)

        if roles:
            # Filter posts by roles
            ltable = s3db.cms_post_role
            q = (ltable.group_id.belongs(roles)) & \
                (ltable.deleted == False)
            rows = db(q).select(ltable.post_id,
                                cache = s3db.cache,
                                groupby = ltable.post_id,
                                )
            post_ids = {row.post_id for row in rows}
            query = (ptable.id.belongs(post_ids)) & query

        posts = db(query).select(ptable.name,
                                 ptable.body,
                                 ptable.date,
                                 ptable.priority,
                                 join = join,
                                 orderby = (~ptable.priority, ~ptable.date),
                                 limitby = (0, 5),
                                 )

        return posts

# =============================================================================
class transferability(CustomController):
    """ Custom controller to update transferability status """

    def __call__(self):

        auth = current.auth
        ADMIN = auth.get_system_roles().ADMIN

        if auth.s3_has_role(ADMIN):

            T = current.T

            form = FORM(H3(T("Check transferability for all current cases")),
                        INPUT(_class="tiny primary button",
                              _type="submit",
                              _value=T("Update now"),
                              ),
                        P("(%s)" % T("This process can take a couple of minutes")),
                        )

            if form.accepts(current.request.post_vars, current.session):

                # Get default site
                default_site = current.deployment_settings.get_org_default_site()

                # Update transferability
                result = update_transferability(site_id=default_site)
                if result:
                    msg = current.T("%(number)s transferable cases found") % {"number": result}
                    current.session.confirmation = msg
                else:
                    msg = current.T("No transferable cases found")
                    current.session.warning = msg

                # Forward to list of transferable cases
                redirect(URL(c = "dvr",
                             f = "person",
                             vars = {"closed": "0",
                                     "dvr_case.transferable__belongs": "True",
                                     "show_family_transferable": "1",
                                     },
                             ))

            self._view(THEME, "transferability.html")
            return {"form": form}

        else:
            auth.permission.fail()

# =============================================================================
class surplus_meals(CustomController):
    """
        Custom controller to register surplus meals
    """

    def __call__(self):

        from gluon import IS_INT_IN_RANGE
        from core import FS, \
                         crud_request, \
                         BasicCRUD, \
                         TextFilter, \
                         DateFilter, \
                         CustomForm

        s3 = current.response.s3
        controller = self.__class__.__name__

        list_url = URL(args=[controller], vars={})

        def prep(r):

            SURPLUS_MEALS = "SURPLUS-MEALS"

            T = current.T
            db = current.db
            s3db = current.s3db

            resource = r.resource

            # Set default SURPLUS_MEALS event type
            ttable = s3db.dvr_case_event_type
            query = (ttable.code == SURPLUS_MEALS) & \
                    (ttable.deleted != True)
            event_type = db(query).select(ttable.id,
                                          limitby = (0, 1),
                                          ).first()
            if not event_type:
                r.error(400, "No event type with code %s defined" % SURPLUS_MEALS)
            event_type_id = event_type.id

            # Filter to SURPLUS_MEALS events without person_id
            query = (FS("type_id") == event_type_id) & \
                    (FS("person_id") == None)
            resource.add_filter(query)

            # Configure fields
            table = resource.table

            field = table.person_id
            field.default = None
            field.readable = field.writable = False

            field = table.type_id
            field.default = event_type_id
            field.readable = field.writable = False

            field = table.date
            field.readable = field.writable = True

            field = table.quantity
            field.default = 0
            # Override IS_EMPTY_OR
            field.requires = IS_INT_IN_RANGE(0, None)
            field.readable = field.writable = True

            field = table.modified_by
            field.readable = True
            registered_by = (T("Registered by"), "modified_by")

            if r.interactive:
                # Custom CRUD form
                crud_form = CustomForm("date",
                                       "quantity",
                                       registered_by,
                                       "comments",
                                       )
                # Custom filter widgets
                filter_widgets = [TextFilter(["created_by$email",
                                              "comments",
                                              ],
                                             label = T("Search"),
                                             ),
                                  DateFilter("date"),
                                  ]

                resource.configure(crud_form = crud_form,
                                   filter_widgets = filter_widgets,
                                   )

                # Turn off filter manager
                current.deployment_settings.search.filter_manager = False

            # Custom list fields
            list_fields = ["date",
                           "quantity",
                           registered_by,
                           "comments",
                           ]

            resource.configure(insertable = True,
                               list_fields = list_fields,
                               # Fix redirects:
                               create_next = list_url,
                               update_next = list_url,
                               delete_next = list_url,
                               )

            # Custom CRUD strings
            T = current.T
            s3.crud_strings["dvr_case_event"] = Storage(
                label_create = T("Register Surplus Meals Quantity"),
                title_display = T("Surplus Meals Quantity"),
                title_list = T("Surplus Meals"),
                title_update = T("Edit Surplus Meals Quantity"),
                label_list_button = T("List Surplus Meals"),
                label_delete_button = T("Delete Entry"),
                msg_record_created = T("Entry added"),
                msg_record_modified = T("Entry updated"),
                msg_record_deleted = T("Entry deleted"),
                msg_list_empty = T("No Surplus Meals currently registered"),
            )

            return True
        s3.prep = prep

        def postp(r, output):

            if isinstance(output, dict):

                # Inject controller name in dt action buttons
                if r.component:
                    action_args = [controller, r.id, r.component.alias, '[id]']
                else:
                    action_args = [controller, '[id]']
                action_url = lambda action: URL(args=action_args + [action], vars={})
                BasicCRUD.action_buttons(r,
                                         read_url = action_url('read'),
                                         update_url = action_url('update'),
                                         delete_url = action_url('delete'),
                                         )

                # Inject controller name in CRUD buttons
                buttons = output.get("buttons")
                if buttons:
                    path = "%s/%s" % (r.controller, r.function)
                    full = "%s/%s" % (path, controller)
                    for element in buttons.values():
                        if not hasattr(element, "attributes"):
                            continue
                        url = element.attributes.get("_href")
                        if url:
                            element["_href"] = url.replace(path, full)

            return output
        s3.postp = postp

        # Custom REST request
        request_args = current.request.args[1:]
        r = crud_request("dvr", "case_event",
                         args = request_args,
                         extension = current.auth.permission.format,
                         )

        return r(dtargs = {"dt_ajax_url": list_url})

# =============================================================================
def update_transferability(site_id=None):
    """
        Update transferability status of all cases, to be called either
        from scheduler task or manually through custom controller.

        Args:
            site_id: the site to check for transferability of cases
    """

    db = current.db
    s3db = current.s3db

    now = current.request.utcnow

    from dateutil.relativedelta import relativedelta
    TODAY = now.date()
    ONE_YEAR_AGO = (now - relativedelta(years=1)).date()

    ptable = s3db.pr_person
    ctable = s3db.dvr_case
    stable = s3db.dvr_case_status
    ftable = s3db.dvr_case_flag
    cftable = s3db.dvr_case_flag_case
    utable = s3db.cr_shelter_unit
    rtable = s3db.cr_shelter_registration
    ttable = s3db.dvr_case_appointment_type
    atable = s3db.dvr_case_appointment

    # Appointment status "completed"
    COMPLETED = 4

    # Appointment statuses which override the requirement
    NOT_REQUIRED = 7

    # Set transferable=False for all cases
    query = (ctable.deleted != True)
    db(query).update(transferable = False,
                     household_transferable = False,
                     )

    # Get IDs of "Reported Transferable" and "Transfer" appointment types
    query = ((ttable.name == "Reported Transferable") | \
             (ttable.name == "Transfer")) & \
            (ttable.deleted != True)
    rows = db(query).select(ttable.id, limitby = (0, 2))
    if rows:
        transferability_complete = set(row.id for row in rows)
    else:
        transferability_complete = None

    # Get IDs of open case statuses
    query = ((stable.is_closed == False) | \
             (stable.is_closed == None)) & \
            (stable.deleted != True)
    rows = db(query).select(stable.id)
    if rows:
        OPEN = set(row.id for row in rows)
    else:
        OPEN = None

    # Get IDs of non-transferable case flags
    query = (ftable.is_not_transferable == True) & \
            (ftable.deleted != True)
    rows = db(query).select(ftable.id)
    if rows:
        NOT_TRANSFERABLE = set(row.id for row in rows)
    else:
        NOT_TRANSFERABLE = None

    # Define age groups (minimum age, maximum age, appointments, maximum absence)
    age_groups = {"children": (None, 15, "mandatory_children", None),
                  "adolescents": (15, 18, "mandatory_adolescents", None),
                  "adults": (18, None, "mandatory_adults", 4),
                  }

    # Define left joins for base criteria
    left = [stable.on(stable.id == ctable.status_id),
            ptable.on(ptable.id == ctable.person_id),
            rtable.on((rtable.person_id == ptable.id) &
                      (rtable.deleted != True)),
            utable.on(utable.id == rtable.shelter_unit_id),
            ]

    # Add left join for "reported transferable" date
    if transferability_complete:
        tctable = atable.with_alias("transferability_complete")
        tcjoin = tctable.on((tctable.person_id == ctable.person_id) & \
                            (tctable.type_id.belongs(transferability_complete)) & \
                            (tctable.deleted != True) & \
                            (tctable.date != None) & \
                            (tctable.date >= ONE_YEAR_AGO) & \
                            (tctable.date <= TODAY) & \
                            (tctable.status == COMPLETED))
        left.append(tcjoin)

    # Add left join for non-transferable case flags
    if NOT_TRANSFERABLE:
        cfjoin = cftable.on((cftable.person_id == ctable.person_id) & \
                            (cftable.flag_id.belongs(NOT_TRANSFERABLE)) & \
                            (cftable.deleted != True))
        left.append(cfjoin)

    result = 0
    for age_group in age_groups:

        min_age, max_age, appointment_flag, maximum_absence = age_groups[age_group]

        # Translate Age Group => Date of Birth
        dob_query = (ptable.date_of_birth != None)
        if max_age:
            dob_min = now - relativedelta(years=max_age)
            dob_query &= (ptable.date_of_birth > dob_min)
        if min_age:
            dob_max = now - relativedelta(years=min_age)
            dob_query &= (ptable.date_of_birth <= dob_max)

        # Case must be valid
        case_query = (ctable.deleted != True) & \
                     ((ctable.archived == False) | \
                      (ctable.archived == None))
        if OPEN:
            # Check only open cases
            case_query &= ctable.status_id.belongs(OPEN)

        # Check for site
        if site_id:
            case_query &= (ctable.site_id == site_id)

        # Case must not have a non-transferable status
        case_query &= (stable.is_not_transferable == False) | \
                      (stable.is_not_transferable == None)

        # Case must not have a non-transferable case flag
        if NOT_TRANSFERABLE:
            case_query &= (cftable.id == None)

        # Person must be assigned to a non-transitory housing unit
        case_query &= (utable.id != None) & \
                      ((utable.transitory == False) | \
                       (utable.transitory == None))

        # Add date-of-birth query
        case_query &= dob_query

        # Check that transferability management is not complete
        # (=no completed appointment for "Reported Transferable" or "Transfer")
        if transferability_complete:
            case_query &= (tctable.id == None)

        # Filter by presence if required
        if maximum_absence is not None:
            if maximum_absence:
                # Must be checked-in or checked-out for less
                # than maximum_absence days
                earliest_check_out_date = now - \
                                          relativedelta(days = maximum_absence)
                presence_query = (rtable.registration_status == 2) | \
                                 ((rtable.registration_status == 3) & \
                                  (rtable.check_out_date > earliest_check_out_date))
            else:
                # Must be checked-in or checked-out
                presence_query = (rtable.registration_status.belongs(2, 3))
            case_query &= presence_query

        # Select all cases for this age group:
        cases = db(case_query).select(ctable.id, left = left)
        case_ids = set(case.id for case in cases)

        if case_ids:

            # Check for mandatory appointments
            query = ctable.id.belongs(case_ids)
            aleft = []

            # Get all mandatory appointment types for this age groups:
            if appointment_flag:
                tquery = (ttable[appointment_flag] == True) & \
                         (ttable.deleted != True)
                rows = db(tquery).select(ttable.id)
                mandatory_appointments = [row.id for row in rows]
            else:
                mandatory_appointments = None

            if mandatory_appointments:

                # Join the valid appointment dates
                for appointment_type_id in mandatory_appointments:

                    alias = "appointments_%s" % appointment_type_id
                    atable_ = atable.with_alias(alias)

                    join = atable_.on((atable_.person_id == ctable.person_id) & \
                                      (atable_.type_id == appointment_type_id) & \
                                      (atable_.deleted != True) & \
                                      (((atable_.status == COMPLETED) & \
                                        (atable_.date != None) & \
                                        (atable_.date >= ONE_YEAR_AGO) & \
                                        (atable_.date <= TODAY)) | \
                                        (atable_.status == NOT_REQUIRED)))
                    aleft.append(join)
                    query &= (atable_.id != None)

                # Select all cases that have the required appointment dates
                cases = db(query).select(ctable.id, left=aleft)
                case_ids = set(case.id for case in cases)

            # Set the matching cases transferable=True
            success = db(ctable.id.belongs(case_ids)).update(transferable=True)
            if success:
                result += success

    # Check transferability of families
    gtable = s3db.pr_group
    mtable = s3db.pr_group_membership
    # Family = Case Group (group type 7)
    query = (gtable.group_type == 7) & \
            (gtable.deleted != True) & \
            (ctable.id != None)

    # Find all case groups which have no currently transferable member
    left = [mtable.on((mtable.group_id == gtable.id) & \
                      (mtable.deleted != True)),
            ctable.on((ctable.person_id == mtable.person_id) &
                      (ctable.transferable == True)),
            ]
    members = ctable.id.count()
    rows = db(query).select(gtable.id,
                            groupby = gtable.id,
                            having = (members == 0),
                            left = left,
                            )
    group_ids = set(row.id for row in rows)

    # Add all case groups which have at least one non-transferable member
    open_case = (ctable.archived != True) & \
                (ctable.deleted != True)
    if OPEN:
        open_case = (ctable.status_id.belongs(OPEN)) & open_case

    if group_ids:
        query &= (~(gtable.id.belongs(group_ids)))
    left = [mtable.on((mtable.group_id == gtable.id) & \
                      (mtable.deleted != True)),
            ctable.on((ctable.person_id == mtable.person_id) & \
                      open_case & \
                      ((ctable.transferable == False) | \
                       (ctable.transferable == None))),
            ]
    if transferability_complete:
        left.append(tcjoin)
        query &= (tctable.id == None)

    rows = db(query).select(gtable.id,
                            groupby = gtable.id,
                            left = left,
                            )
    group_ids |= set(row.id for row in rows)

    # Find all cases which do not belong to any of these
    # non-transferable case groups, but either belong to
    # another case group or are transferable themselves
    ftable = mtable.with_alias("family")
    left = [mtable.on((mtable.person_id == ctable.person_id) & \
                      (mtable.group_id.belongs(group_ids)) & \
                      (mtable.deleted != True)),
            ftable.on((ftable.person_id == ctable.person_id) & \
                      (ftable.deleted != True)),
            gtable.on((gtable.id == ftable.group_id) & \
                      (gtable.group_type == 7)),
            ]
    query = (mtable.id == None) & (ctable.deleted != True)
    families = gtable.id.count()
    required = ((families > 0) | (ctable.transferable == True))
    rows = db(query).select(ctable.id,
                            groupby = ctable.id,
                            having = required,
                            left = left,
                            )

    # ...and set them household_transferable=True:
    case_ids = set(row.id for row in rows)
    if case_ids:
        db(ctable.id.belongs(case_ids)).update(household_transferable=True)

    return result

# END =========================================================================
