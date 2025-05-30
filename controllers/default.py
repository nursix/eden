"""
    Default Controllers
"""

#module = "default"

# -----------------------------------------------------------------------------
def index():
    """
        Main Home Page
    """

    auth.settings.register_onvalidation = _register_validation
    auth.configure_user_fields()

    current.menu.oauth = MainMenu.menu_oauth()

    page = None
    if len(request.args):
        # Use the first non-numeric argument as page name
        # (RESTful custom controllers may have record IDs in Ajax URLs)
        for arg in request.args:
            pname = arg.split(".", 1)[0] if "." in arg else arg
            if not pname.isdigit():
                page = pname
                break

    # Module name for custom controllers
    name = "controllers"

    custom = None
    templates = settings.get_template()

    if page:
        # Go to a custom page,
        # - args[0] = name of the class in /modules/templates/<template>/controllers.py
        # - other args & vars passed through
        if not isinstance(templates, (tuple, list)):
            templates = (templates,)
        for template in templates[::-1]:
            package = "applications.%s.modules.templates.%s" % (appname, template)
            try:
                custom = getattr(__import__(package, fromlist = [name]), name)
            except (ImportError, AttributeError):
                # No Custom Page available, continue with the default
                #page = "modules/templates/%s/controllers.py" % template
                #current.log.warning("File not loadable",
                #                    "%s, %s" % (page, sys.exc_info()[1]))
                continue
            else:
                if hasattr(custom, page):
                    controller = getattr(custom, page)()
                elif page != "login":
                    raise HTTP(404, "Function not found: %s()" % page)
                else:
                    controller = custom.index()
                output = controller()
                return output

    elif templates != "default":
        # Try a Custom Homepage
        if not isinstance(templates, (tuple, list)):
            templates = (templates,)
        for template in templates[::-1]:
            package = "applications.%s.modules.templates.%s" % (appname, template)
            try:
                custom = getattr(__import__(package, fromlist = [name]), name)
            except (ImportError, AttributeError):
                # No Custom Page available, continue with the next option, or default
                # @ToDo: cache this result in session
                #import sys
                #current.log.warning("Custom homepage cannot be loaded", sys.exc_info()[1])
                continue
            else:
                if hasattr(custom, "index"):
                    output = custom.index()()
                    return output

    # Default homepage
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
        posts = s3db.cms_announcements(roles=filter_roles)

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
        login_div = DIV(H3(T("Login")))
        auth.messages.submit_button = T("Login")
        login_form = auth.login(inline=True)

    output = {"login_div": login_div,
              "login_form": login_form,
              "announcements": announcements,
              "announcements_title": announcements_title,
              }

    return output

# -----------------------------------------------------------------------------
def about():
    """
        The About page provides details on the software dependencies and
        versions available to this instance of Sahana Eden.
    """

    _custom_view("about")

    # Allow editing of page content from browser using CMS module
    if settings.has_module("cms"):
        ADMIN = auth.s3_has_role("ADMIN")
        table = s3db.cms_post
        ltable = s3db.cms_post_module
        module = "default"
        resource = "about"
        query = (ltable.module == module) & \
                ((ltable.resource == None) | \
                 (ltable.resource == resource)) & \
                (ltable.post_id == table.id) & \
                (table.deleted != True)
        item = db(query).select(table.id,
                                table.body,
                                limitby = (0, 1)
                                ).first()

        get_vars = {"module": module,
                    "resource": resource,
                    }

        if item:
            from core import XMLContentsRepresent
            contents = XMLContentsRepresent(item.body)
            if ADMIN:
                item = DIV(contents,
                           BR(),
                           A(T("Edit"),
                             _href=URL(c="cms", f="post",
                                       args = [item.id, "update"],
                                       vars = get_vars,
                                       ),
                             _class="action-btn"))
            else:
                item = DIV(contents)
        elif ADMIN:
            item = A(T("Edit"),
                     _href=URL(c="cms", f="post",
                               args = "create",
                               vars = get_vars,
                               ),
                     _class="action-btn cms-edit")
        else:
            item = H2(T("About"))
    else:
        item = H2(T("About"))

    response.title = T("About")

    if not settings.get_security_version_info() or \
       settings.get_security_version_info_requires_login() and \
       not auth.s3_logged_in():
        details = ""
    else:
        from core import system_info
        details = system_info()

    return {"item": item,
            "details": details,
            }

# -----------------------------------------------------------------------------
def audit():
    """
        RESTful CRUD Controller for Audit Logs
        - used e.g. for Site Activity
    """

    return crud_controller("s3", "audit")

# -----------------------------------------------------------------------------
#def call():
#    """
#        Call an XMLRPC, JSONRPC or RSS service
#        - NB This is currently unused in Sahana Eden
#    """

#    # If webservices don't use sessions, avoid cluttering up the storage
#    #session.forget()
#    return service()

# -----------------------------------------------------------------------------
def contact():
    """
        Give the user options to contact the site admins.
        Either:
            An internal Support Requests database
        or:
            Custom View
    """

    if auth.is_logged_in() and settings.has_module("support"):
        # Provide an internal Support Requests ticketing system.
        prefix = "support"
        resourcename = "req"
        tablename = "%s_%s" % (prefix, resourcename)
        table = s3db[tablename]

        # Pre-processor
        def prep(r):
            if r.interactive:
                # Only Admins should be able to update ticket status
                status = table.status
                actions = table.actions
                if not auth.s3_has_role("ADMIN"):
                    status.writable = False
                    actions.writable = False
                if r.method != "update":
                    status.readable = False
                    status.writable = False
                    actions.readable = False
                    actions.writable = False
            return True
        s3.prep = prep

        return crud_controller(prefix, resourcename)

    templates = settings.get_template()
    if templates != "default":
        # Try a Custom Controller
        if not isinstance(templates, (tuple, list)):
            templates = (templates,)
        for template in templates[::-1]:
            package = "applications.%s.modules.templates.%s" % (appname, template)
            name = "controllers"
            try:
                custom = getattr(__import__(package, fromlist=[name]), name)
            except (ImportError, AttributeError):
                # No Custom Page available, try a custom view
                pass
            else:
                if hasattr(custom, "contact"):
                    controller = getattr(custom, "contact")()
                    return controller()

        # Try a Custom View
        for template in templates:
            view = os.path.join(request.folder,
                                "modules",
                                "templates",
                                template,
                                "views",
                                "contact.html")
            if os.path.exists(view):
                try:
                    # Pass view as file not str to work in compiled mode
                    response.view = open(view, "rb")
                except IOError:
                    from gluon.http import HTTP
                    raise HTTP("404", "Unable to open Custom View: %s" % view)

                response.title = T("Contact us")
                return {}

    if settings.has_module("cms"):
        # Use CMS
        return s3db.cms_index("default", "contact",
                              page_name = T("Contact Us"))

    # Just use default HTML View
    return {}

# -----------------------------------------------------------------------------
def download():
    """
        Download a file
    """

    try:
        filename = request.args[0]
    except:
        # No legitimate interactive request comes here without a filename,
        # so this hits mainly non-interactive clients, and those do not
        # recognize an error condition from a HTTP 303 => better to raise
        # a proper error than to redirect:
        raise HTTP(400, "No file specified")
        #session.error = T("Need to specify the file to download!")
        #redirect(URL(f="index"))

    import re
    from pydal.helpers.regex import REGEX_UPLOAD_PATTERN
    items = re.match(REGEX_UPLOAD_PATTERN, filename)
    if not items:
        raise HTTP(404)
    tablename = items.group("table")
    fieldname = items.group("field")

    # Check Permissions
    if "_" in tablename:
        # Load the Model, deal with aliased tables
        otn = request.vars.get("otn")
        if otn and tablename != otn:
            alias, tablename = tablename, otn
            table = s3db.table(tablename)
            if table:
                table = table.with_alias(alias)
        else:
            alias = tablename
            table = s3db.table(tablename)

        if table:
            # Identify the record
            try:
                query = (table[fieldname] == filename)
                row = current.db(query).select(table._id, limitby=(0, 1)).first()
            except (AttributeError, KeyError) as e:
                # Field does not exist in table
                raise HTTP(404)
            else:
                record_id = row[table._id] if row else None

            # Check permission
            # NOTE
            # If no record ID can be found, then the file does not belong
            # to this table, and hence cannot be accessed by this link,
            # which is therefore indicated as failed authorization
            if not record_id or \
               not auth.s3_has_permission("read", tablename, record_id=record_id):
                auth.permission.fail()
        else:
            # Table does not exist
            raise HTTP(404)

    return response.download(request, db)

# -----------------------------------------------------------------------------
def get_settings():
    """
       Function to lookup the value of one or more deployment_settings
           Responds to GET requests.
           Requires admin permissions
           Used by edentest_robot.py
    """

    # Check if the request has a valid authorization header with admin cred.
    if not auth.s3_has_role("ADMIN"):
        auth.permission.format = None
        auth.permission.fail()

    elif not settings.get_base_allow_testing():
        raise HTTP("405", "Testing not allowed")

    else:
        # Example request: /get_settings/template
        asked = request.args
        return_settings = {}

        for setting in asked:
            func_name = "get_%s" % setting
            function = getattr(settings, func_name)
            # Example function: settings.get_template()
            try:
                value = function()
            except TypeError:
                continue

            return_settings[setting] = value

        return response.json(return_settings)

# -----------------------------------------------------------------------------
def group():
    """
        RESTful CRUD controller
        - needed when group add form embedded in default/person
        - only create method is allowed, when opened in an inline form.
    """

    # Check if it is called from a inline form
    if auth.permission.format != "popup":
        return ""

    # Pre-process
    def prep(r):
        if r.method != "create":
            return False
        return True
    s3.prep = prep

    return crud_controller("pr", "group")

# -----------------------------------------------------------------------------
def help():
    """ CMS page or Custom View """

    _custom_view("help")

    # Allow editing of page content from browser using CMS module
    if settings.has_module("cms"):
        ADMIN = auth.s3_has_role("ADMIN")
        table = s3db.cms_post
        ltable = s3db.cms_post_module
        module = "default"
        resource = "help"
        query = (ltable.module == module) & \
                ((ltable.resource == None) | \
                 (ltable.resource == resource)) & \
                (ltable.post_id == table.id) & \
                (table.deleted != True)
        item = db(query).select(table.id,
                                table.body,
                                limitby=(0, 1)).first()

        get_vars = {"module": module,
                    "resource": resource,
                    }

        if item:
            if ADMIN:
                item = DIV(XML(item.body),
                           BR(),
                           A(T("Edit"),
                             _href=URL(c="cms", f="post",
                                       args=[item.id, "update"],
                                       vars=get_vars,
                                       ),
                             _class="action-btn"))
            else:
                item = DIV(XML(item.body))
        elif ADMIN:
            item = A(T("Edit"),
                     _href=URL(c="cms", f="post",
                               args="create",
                               vars=get_vars,
                               ),
                     _class="action-btn cms-edit")
        else:
            item = TAG[""](H2(T("Help")),
                           A(T("User & Administration Guide"),
                            _href="http://eden.sahanafoundation.org/wiki/UserGuidelines",
                            _target="_blank"),
                           " - online version")
    else:
        item = TAG[""](H2(T("Help")),
                       A(T("User & Administration Guide"),
                         _href="http://eden.sahanafoundation.org/wiki/UserGuidelines",
                         _target="_blank"),
                         " - online version")

    response.title = T("Help")

    return {"item": item}

# -----------------------------------------------------------------------------
def masterkey():
    """ Master Key Verification and Context Query """

    # Challenge the client to login with master key
    if not auth.s3_logged_in():
        auth.permission.fail()

    # If successfully logged-in, provide context information for
    # the master key (e.g. project UUID + title, master key UUID)
    from core.aaa.masterkey import S3MasterKey
    return S3MasterKey.context()

# -----------------------------------------------------------------------------
def message():
    """ Show a confirmation screen """

    #if "verify_email_sent" in request.args:
    title = T("Account Registered - Please Check Your Email")
    message = T( "%(system_name)s has sent an email to %(email)s to verify your email address.\nPlease check your email to verify this address. If you do not receive this email please check you junk email or spam filters." )\
                 % {"system_name": settings.get_system_name(),
                    "email": request.vars.email}
    image = "email_icon.png"

    return {"title": title,
            "message": message,
            "image_src": "/%s/static/img/%s" % (appname, image),
            }

# -----------------------------------------------------------------------------
def page():
    """
        Show a custom CMS page
    """

    try:
        page = request.args[0]
    except:
        raise HTTP(400, "Page not specified")

    # Find a post with the given page name that is linked to this controller:
    ctable = s3db.cms_post
    ltable = s3db.cms_post_module
    join = ltable.on((ltable.post_id == ctable.id) & \
                     (ltable.module == "default") & \
                     (ltable.resource == "page") & \
                     (ltable.deleted == False))

    query = (ctable.name == page) & \
            (ctable.deleted == False)
    row = db(query).select(ctable.id,
                           ctable.title,
                           ctable.body,
                           join = join,
                           cache = s3db.cache,
                           limitby = (0, 1),
                           ).first()
    try:
        title = row.title
    except:
        raise HTTP(404, "Page not found in CMS")

    if row.body:
        from io import StringIO
        try:
            body = current.response.render(StringIO(row.body), {})
        except:
            body = row.body
    else:
        body = ""
    item = DIV(XML(body), _class="cms-item")

    if auth.s3_has_role("ADMIN"):
        # Add edit-action
        item.append(BR())
        item.append(A(current.T("Edit"),
                    _href = URL(c="cms", f="post",
                                args = [row.id, "update"],
                                vars = {"page": page},
                                ),
                    _class = "action-btn",
                    ))

    response.title = title
    _custom_view("page")

    return {"item": item,
            }

# -----------------------------------------------------------------------------
def person():
    """
        Profile to show:
         - User Details
         - Person Details
         - Staff/Volunteer Record
         - Map Config
    """

    # Get person_id of current user
    if auth.s3_logged_in():
        person_id = str(auth.s3_logged_in_person())
    else:
        person_id = None

    # Fix request args:
    # - leave as-is if this is an options/validate Ajax-request
    # - otherwise, make sure person_id is the first argument
    request_args = request.args
    if not request_args or \
       request_args[0] != person_id and \
       request_args[-1] not in ("options.s3json", "validate.json"):
        if not person_id:
            # Call to profile before login (e.g. from link in welcome email)
            # => redirect to login, then return here
            redirect(URL(f = "user",
                         args = ["login"],
                         vars = {"_next": URL(f="person", args=request_args)},
                         ))
        request.args = [person_id]

    if settings.get_auth_profile_controller() == "hrm":
        table = s3db.hrm_human_resource
        query = (table.person_id == person_id) & \
                (table.deleted == False)
        hr = db(query).select(table.id,
                              limitby = (0, 1)
                              )
        if hr:
            # Use the HRM controller/rheader
            request.get_vars["profile"] = 1
            return s3db.hrm_person_controller()

    # Use the PR controller/rheader

    set_method = s3db.set_method

    # Custom Method for User
    def auth_profile_method(r, **attr):
        # Custom View
        response.view = "update.html"
        current.menu.breadcrumbs = None

        # RHeader for consistency
        rheader = attr.get("rheader", None)
        if callable(rheader):
            rheader = rheader(r)

        table = auth.settings.table_user
        tablename = table._tablename

        next = URL(c = "default",
                   f = "person",
                   args = [person_id,
                           "user_profile",
                           ],
                   )
        onaccept = lambda form: auth.s3_approve_user(form.vars),
        auth.configure_user_fields()
        form = auth.profile(next = next,
                            onaccept = onaccept)

        return {"title": s3.crud_strings["pr_person"]["title_display"],
                "rheader": rheader,
                "form": form,
                }

    set_method("pr_person",
               method = "user_profile",
               action = auth_profile_method)

    # Custom Method for Contacts
    set_method("pr_person",
               method = "contacts",
               action = s3db.pr_Contacts)

    #if settings.has_module("asset"):
    #    # Assets as component of people
    #    s3db.add_components("pr_person", asset_asset="assigned_to_id")

    # CRUD pre-process
    def prep(r):
        if r.method in ("options", "validate"):
            return True
        if r.interactive and r.method != "import":
            # Load default model to override CRUD Strings
            tablename = "pr_person"
            table = s3db[tablename]

            # Users can not delete their own person record
            r.resource.configure(deletable = False)

            s3.crud_strings[tablename].update(
                title_display = T("Personal Profile"),
                title_update = T("Personal Profile"))

            if r.component:
                if r.component_name == "physical_description":
                    # Hide all but those details that we want
                    # Lock all the fields
                    table = r.component.table
                    for field in table.fields:
                        table[field].writable = False
                        table[field].readable = False
                    # Now enable those that we want
                    table.ethnicity.writable = True
                    table.ethnicity.readable = True
                    table.blood_type.writable = True
                    table.blood_type.readable = True
                    table.medical_conditions.writable = True
                    table.medical_conditions.readable = True
                    table.other_details.writable = True
                    table.other_details.readable = True

                elif r.component_name == "human_resource":
                    r.component.configure(insertable = False,
                                          deletable = False,
                                          )

                elif r.component_name == "config":
                    ctable = s3db.gis_config
                    s3db.gis_config_form_setup()

                    # Create forms use this
                    # (update forms are in gis/config())
                    crud_fields = ["name",
                                   "pe_default",
                                   "default_location_id",
                                   "zoom",
                                   "lat",
                                   "lon",
                                   #"projection_id",
                                   #"symbology_id",
                                   #"wmsbrowser_url",
                                   #"wmsbrowser_name",
                                   ]
                    osm_table = s3db.gis_layer_openstreetmap
                    openstreetmap = db(osm_table.deleted == False).select(osm_table.id,
                                                                          limitby=(0, 1))
                    if openstreetmap:
                        # OpenStreetMap config
                        s3db.add_components("gis_config",
                                            auth_user_options = {"joinby": "pe_id",
                                                                 "pkey": "pe_id",
                                                                 "multiple": False,
                                                                 },
                                           )
                        crud_fields += ["user_options.osm_oauth_consumer_key",
                                        "user_options.osm_oauth_consumer_secret",
                                        ]
                    crud_form = s3base.CustomForm(*crud_fields)
                    list_fields = ["name",
                                   "pe_default",
                                   ]
                    s3db.configure("gis_config",
                                   crud_form = crud_form,
                                   insertable = False,
                                   list_fields = list_fields,
                                   )
            else:
                table.pe_label.readable = False
                table.pe_label.writable = False
                table.missing.readable = False
                table.missing.writable = False
                table.age_group.readable = False
                table.age_group.writable = False
                # Assume volunteers only between 12-81
                dob = table.date_of_birth
                dob.widget = S3CalendarWidget(past_months = 972,
                                              future_months = -144,
                                              )
            return True
        else:
            # Disable non-interactive & import
            return False
    s3.prep = prep

    # CRUD post-process
    def postp(r, output):

        if r.interactive:
            if not r.component and r.record and isinstance(output, dict):
                # Remove all CRUD buttons except Edit-button
                buttons = output.get("buttons")
                if isinstance(buttons, dict):
                    output["buttons"] = {"edit_btn": buttons["edit_btn"]} \
                                        if "edit_btn" in buttons else {}

            elif r.component_name == "config":
                update_url = URL(c="gis", f="config", args="[id]")
                s3_action_buttons(r, update_url=update_url)
                s3.actions.append({"url": URL(c="gis", f="index", vars={"config":"[id]"}),
                                   "label": str(T("Show")),
                                   "_class": "action-btn",
                                   })

            elif r.component_name == "asset":
                # Provide a link to assign a new Asset
                # @ToDo: Proper Widget to do this inline
                output["add_btn"] = A(T("Assign Asset"),
                                      _href=URL(c="asset", f="asset"),
                                      _id="add-btn",
                                      _class="action-btn",
                                      )
        return output
    s3.postp = postp

    if settings.get_hrm_record_tab():
        hr_tab = (T("Staff/Volunteer Record"), "human_resource")
    else:
        hr_tab = None

    if settings.get_hrm_staff_experience() == "experience":
        experience_tab = (T("Experience"), "experience")
    else:
        experience_tab = None

    if settings.get_hrm_use_certificates():
        certificates_tab = (T("Certificates"), "certificate")
    else:
        certificates_tab = None

    if settings.get_hrm_use_credentials():
        credentials_tab = (T("Credentials"), "credential")
    else:
        credentials_tab = None

    if settings.get_hrm_use_description():
        description_tab = (T("Description"), "physical_description")
    else:
        description_tab = None

    if settings.get_pr_use_address():
        address_tab = (T("Address"), "address")
    else:
        address_tab = None

    if settings.get_hrm_use_education():
        education_tab = (T("Education"), "education")
    else:
        education_tab = None

    if settings.get_hrm_use_id():
        id_tab = (T("ID"), "identity")
    else:
        id_tab = None

    if settings.get_hrm_use_skills():
        skills_tab = (T("Skills"), "competency")
    else:
        skills_tab = None

    teams = settings.get_hrm_teams()
    if teams:
        teams_tab = (T(teams), "group_membership")
    else:
        teams_tab = None

    if settings.get_hrm_use_trainings():
        trainings_tab = (T("Trainings"), "training")
    else:
        trainings_tab = None

    setting = settings.get_pr_contacts_tabs()
    if setting:
        contacts_tab = (settings.get_pr_contacts_tab_label(), "contacts")
    else:
        contacts_tab = None

    tabs = [(T("Person Details"), None),
            (T("User Account"), "user_profile"),
            hr_tab,
            id_tab,
            description_tab,
            address_tab,
            contacts_tab,
            education_tab,
            trainings_tab,
            certificates_tab,
            skills_tab,
            credentials_tab,
            experience_tab,
            teams_tab,
            #(T("Assets"), "asset"),
            #(T("My Subscriptions"), "subscription"),
            (T("My Maps"), "config"),
            ]

    return crud_controller("pr", "person",
                           rheader = lambda r, t=tabs: s3db.pr_rheader(r, tabs=t),
                           )

# -----------------------------------------------------------------------------
def privacy():
    """ Custom View """

    _custom_view("privacy")

    response.title = T("Privacy")
    return {}

# -----------------------------------------------------------------------------
def public_url():
    """ Simple check for use in monitoring scripts """

    return settings.get_base_public_url()

# -----------------------------------------------------------------------------
def rapid():
    """ Set/remove rapid data entry flag """

    val = get_vars.get("val", True)
    if val == "0":
        val = False
    else:
        val = True
    session.s3.rapid_data_entry = val

    response.view = "xml.html"
    return {"item": str(session.s3.rapid_data_entry)}

# -----------------------------------------------------------------------------
def site():
    """
        @ToDo: Avoid redirect
    """

    try:
        site_id = request.args[0]
    except:
        raise HTTP(404)

    table = s3db.org_site
    record = db(table.site_id == site_id).select(table.instance_type,
                                                 limitby=(0, 1)).first()
    tablename = record.instance_type
    table = s3db.table(tablename)
    if table:
        query = (table.site_id == site_id)
        id = db(query).select(table.id,
                              limitby = (0, 1)).first().id
        cf = tablename.split("_", 1)
        redirect(URL(c = cf[0],
                     f = cf[1],
                     args = [id]))

# -----------------------------------------------------------------------------
def skill():
    """
        RESTful CRUD controller
        - needed when skill add form embedded in default/person
        - only create method is allowed, when opened in an inline form.
    """

    # Check if it is called from a inline form
    if auth.permission.format != "popup":
        return ""

    # Pre-process
    def prep(r):
        if r.method != "create":
            return False
        return True
    s3.prep = prep

    return crud_controller("hrm", "skill")

# -----------------------------------------------------------------------------
def tables():
    """
        RESTful CRUD Controller for Dynamic Table Models
    """

    return crud_controller("s3", "table",
                           rheader = s3db.s3_table_rheader,
                           csv_template = ("s3", "table"),
                           csv_stylesheet = ("s3", "table.xsl"),
                           )

# -----------------------------------------------------------------------------
def table():
    """
        RESTful CRUD Controller for Dynamic Table Contents

        NB: First argument is the resource name, i.e. the name of
            the dynamic table without prefix, e.g.:
            default/table/test to access s3dt_test table
    """

    args = request.args
    if len(args):
        return crud_controller(dynamic = args[0].rsplit(".", 1)[0])
    else:
        raise HTTP(400, "No resource specified")

# -----------------------------------------------------------------------------
def tos():
    """ Custom View """

    _custom_view("tos")

    response.title = T("Terms of Service")
    return {}

# -----------------------------------------------------------------------------
def user():
    """ Auth functions based on arg. See gluon/tools.py """

    auth_settings = auth.settings
    utable = auth_settings.table_user

    arg = request.args(0)
    if arg == "verify_email":
        # Ensure we use the user's language
        key = request.args[-1]
        query = (utable.registration_key == key)
        user = db(query).select(utable.language,
                                limitby=(0, 1)).first()
        if not user:
            redirect(auth_settings.verify_email_next)
        session.s3.language = user.language

    auth_settings.on_failed_authorization = URL(f="error")

    auth.configure_user_fields()
    auth_settings.profile_onaccept = auth.s3_user_profile_onaccept
    auth_settings.register_onvalidation = _register_validation

    # Check for template-specific customisations
    customise = settings.customise_auth_user_controller
    if customise:
        customise(arg = arg)

    self_registration = settings.get_security_self_registration()
    login_form = register_form = None

    current.menu.oauth = MainMenu.menu_oauth()

    if not settings.get_auth_password_changes():
        # Block Password changes as these are managed externally (OpenID / SMTP / LDAP)
        auth_settings.actions_disabled = ("change_password",
                                          "retrieve_password",
                                          )
    elif not settings.get_auth_password_retrieval():
        # Block password retrieval
        auth_settings.actions_disabled = ("retrieve_password",
                                          )

    header = response.s3_user_header or ""

    if arg == "login":
        title = response.title = T("Login")
        # @ToDo: move this code to /modules/s3/s3aaa.py:login()?
        auth.messages.submit_button = T("Login")
        form = auth()
        #form = auth.login()
        login_form = form

    elif arg == "register":
        # @ToDo: move this code to /modules/s3/s3aaa.py:register()?
        if not self_registration:
            session.error = T("Registration not permitted")
            redirect(URL(f="index"))
        if response.title:
            # Customised
            title = response.title
        else:
            # Default
            title = response.title = T("Register")
        form = register_form = auth.register()

    elif arg == "change_password":
        title = response.title = T("Change Password")
        form = auth()
        # Add client-side validation
        js_global = []
        js_append = js_global.append
        js_append('''S3.password_min_length=%i''' % settings.get_auth_password_min_length())
        js_append('''i18n.password_min_chars="%s"''' % T("You must enter a minimum of %d characters"))
        js_append('''i18n.weak="%s"''' % T("Weak"))
        js_append('''i18n.normal="%s"''' % T("Normal"))
        js_append('''i18n.medium="%s"''' % T("Medium"))
        js_append('''i18n.strong="%s"''' % T("Strong"))
        js_append('''i18n.very_strong="%s"''' % T("Very Strong"))
        script = '''\n'''.join(js_global)
        s3.js_global.append(script)
        if s3.debug:
            s3.scripts.append("/%s/static/scripts/jquery.pstrength.2.1.0.js" % appname)
        else:
            s3.scripts.append("/%s/static/scripts/jquery.pstrength.2.1.0.min.js" % appname)
        s3.jquery_ready.append(
'''$('.password:eq(1)').pstrength({
 'minChar': S3.password_min_length,
 'minCharText': i18n.password_min_chars,
 'verdicts': [i18n.weak, i18n.normal, i18n.medium, i18n.strong, i18n.very_strong]
})''')

    elif arg == "retrieve_password":
        title = response.title = T("Lost Password")
        form = auth()

    elif arg == "profile":
        title = response.title = T("User Profile")
        form = auth.profile()

    elif arg == "consent":
        title = response.title = T("Consent")
        form = auth.consent()

    elif arg == "options.s3json":
        # Used when adding organisations from registration form
        return crud_controller(prefix="auth", resourcename="user")

    else:
        # logout or verify_email
        title = ""
        form = auth()

    if form:
        if s3.crud.submit_style:
            form[0][-1][1][0]["_class"] = s3.crud.submit_style

    # Default view
    response.view = "default/user.html"

    templates = settings.get_template()
    if templates != "default":
        # Try a Custom View
        folder = request.folder
        if not isinstance(templates, (tuple, list)):
            templates = (templates,)
        for template in templates[::-1]:
            view = os.path.join(folder,
                                "modules",
                                "templates",
                                template,
                                "views",
                                "user.html")
            if os.path.exists(view):
                try:
                    # Pass view as file not str to work in compiled mode
                    response.view = open(view, "rb")
                except IOError:
                    from gluon.http import HTTP
                    raise HTTP("404", "Unable to open Custom View: %s" % view)
                else:
                    break

    return {"title": title,
            "header": header,
            "form": form,
            "login_form": login_form,
            "register_form": register_form,
            "self_registration": self_registration,
            }

# -----------------------------------------------------------------------------
def video():
    """ Custom View """

    _custom_view("video")

    response.title = T("Video Tutorials")
    return {}

# -----------------------------------------------------------------------------
def view():
    """ Custom View """

    view = request.args(0)

    _custom_view(view)

    response.title = view
    return {}

# =============================================================================
# Login Methods
# =============================================================================
def facebook():
    """ Login using Facebook """

    channel = s3db.msg_facebook_login()

    if not channel:
        redirect(URL(f="user", args=request.args, vars=get_vars))

    from core.aaa.oauth import FaceBookAccount
    auth.settings.login_form = FaceBookAccount(channel)
    form = auth()

    return {"form": form}

# -----------------------------------------------------------------------------
def google():
    """ Login using Google """

    channel = settings.get_auth_google()

    if not channel:
        redirect(URL(f="user", args=request.args, vars=get_vars))

    from core.aaa.oauth import GooglePlusAccount
    auth.settings.login_form = GooglePlusAccount(channel)
    form = auth()

    return {"form": form}

# -----------------------------------------------------------------------------
def humanitarian_id():
    """ Login using Humanitarian.ID """

    channel = settings.get_auth_humanitarian_id()

    if not channel:
        redirect(URL(f="user", args=request.args, vars=get_vars))

    from core.aaa.oauth import HumanitarianIDAccount
    auth.settings.login_form = HumanitarianIDAccount(channel)
    form = auth()

    return {"form": form}

# -----------------------------------------------------------------------------
def openid_connect():
    """ Login using OpenID Connect """

    channel = settings.get_auth_openid_connect()
    if not channel:
        redirect(URL(f="user", args=request.args, vars=get_vars))

    from core.aaa.oauth import OpenIDConnectAccount
    auth.settings.login_form = OpenIDConnectAccount(channel)
    form = auth()

    return {"form": form}

# =============================================================================
# Helpers
# =============================================================================
def _apath(path = ""):
    """ Application path """

    from gluon.fileutils import up
    opath = up(request.folder)
    # @ToDo: This path manipulation is very OS specific.
    while path[:3] == "../": opath, path = up(opath), path[3:]
    return os.path.join(opath, path).replace("\\", "/")

# -----------------------------------------------------------------------------
def _custom_view(filename):
    """
        See if there is a custom view for a page &, if so, use that
    """

    templates = settings.get_template()
    if templates != "default":
        folder = request.folder
        if not isinstance(templates, (tuple, list)):
            templates = (templates,)
        for template in templates[::-1]:
            # Try a Custom View
            view = os.path.join(folder,
                                "modules",
                                "templates",
                                template,
                                "views",
                                "%s.html" % filename)
            if os.path.exists(view):
                try:
                    # Pass view as file not str to work in compiled mode
                    response.view = open(view, "rb")
                except IOError:
                    from gluon.http import HTTP
                    raise HTTP("404", "Unable to open Custom View: %s" % view)
                else:
                    break

# -----------------------------------------------------------------------------
def _register_validation(form):
    """ Validate the fields in registration form """

    form_vars = form.vars

    # Mobile Phone
    mobile = form_vars.get("mobile")
    if mobile:
        import re
        regex = re.compile(SINGLE_PHONE_NUMBER_PATTERN)
        if not regex.match(mobile):
            form.errors.mobile = T("Invalid phone number")
    elif settings.get_auth_registration_mobile_phone_mandatory():
        form.errors.mobile = T("Phone number is required")

    # Home Phone
    home = form_vars.get("home")
    if home:
        import re
        regex = re.compile(SINGLE_PHONE_NUMBER_PATTERN)
        if not regex.match(home):
            form.errors.home = T("Invalid phone number")

    org = settings.get_auth_registration_organisation_default()
    if org:
        # Add to default organisation
        form_vars.organisation_id = org

    return

# END =========================================================================
