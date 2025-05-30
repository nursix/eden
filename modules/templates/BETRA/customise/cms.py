"""
    CMS module customisations for RLPPTM

    License: MIT
"""

from gluon import current, URL, IS_EMAIL

from core import IS_ONE_OF

# -----------------------------------------------------------------------------
def lookup_newsletter_recipients(resource):
    """
        Callback function to look up the recipients corresponding to a
        distribution list entry (in this instance: send all newsletters
        to orgs)

        Args:
            the (filtered) resource

        Returns:
            a list of pe_ids of the recipients
    """

    if resource.tablename == "org_organisation":
        rows = resource.select(["pe_id"], as_rows=True)
        return [row.pe_id for row in rows]

    else:
        return []

# -------------------------------------------------------------------------
def resolve_newsletter_recipient(pe_id):
    """
        Callback function to look up the email address(es) for
        a recipient

        Args:
            pe_id: the pe_id of the recipient

        Returns:
            email address or list of email addresses of the
            recipient
    """

    s3db = current.s3db

    # Retrieve the instance record
    tablename, record_id = s3db.get_instance("pr_pentity", pe_id)
    if tablename == "org_organisation":
        # Send to all ORG_ADMINs
        from ..helpers import get_role_emails
        return get_role_emails("ORG_ADMIN", organisation_id=record_id)

    else:
        # Fall back to default behavior (direct pr_contact lookup)
        return s3db.cms_UpdateNewsletter.resolve(pe_id)

# -------------------------------------------------------------------------
def cms_newsletter_resource(r, tablename):

    s3db = current.s3db

    # Configure callbacks for newsletter distribution
    s3db.configure("cms_newsletter",
                   lookup_recipients = lookup_newsletter_recipients,
                   resolve_recipient = resolve_newsletter_recipient,
                   )

    # Contact email is required
    table = s3db.cms_newsletter
    field = table.contact_email
    field.requires = IS_EMAIL()

# -------------------------------------------------------------------------
def cms_newsletter_controller(**attr):

    db = current.db
    s3db = current.s3db

    s3 = current.response.s3

    # Custom prep
    standard_prep = s3.prep
    def prep(r):
        # Call standard prep
        result = standard_prep(r) if callable(standard_prep) else True

        if r.component_name == "newsletter_recipient":

            record = r.record

            if record.status == "NEW":
                # Allow manual adding of new recipients
                s3db.configure("cms_newsletter_recipient",
                               insertable = True,
                               )

            ctable = s3db.cms_newsletter_recipient
            etable = s3db.pr_pentity

            # Only organisations as recipients
            from core import accessible_pe_query
            types = ["org_organisation"]
            query = accessible_pe_query(instance_types = types,
                                        method = "read",
                                        c = "org",
                                        f = "organisation",
                                        )

            # Filter out existing recipients
            existing = db((ctable.newsletter_id == record.id) &
                          (ctable.deleted == False))._select(ctable.pe_id)
            query &= ~(etable.pe_id.belongs(existing))

            field = ctable.pe_id
            field.requires = IS_ONE_OF(db(query), "pr_pentity.pe_id",
                                       field.represent,
                                       instance_types = types,
                                       )
        return result
    s3.prep = prep

    return attr

# -------------------------------------------------------------------------
def cms_post_resource(r, tablename):

    T = current.T
    s3db = current.s3db

    table = s3db.cms_post

    from core import CustomForm, \
                     InlineComponent, \
                     InlineLink, \
                     s3_text_represent

    field = table.body
    field.label = T("Content")
    field.represent = lambda v, row=None: \
                             s3_text_represent(v, lines=20, _class = "cms-item-body")

    record = r.record
    if r.tablename == "cms_series" and \
        record and record.name == "Announcements":
        field = table.priority
        field.readable = field.writable = True

        crud_fields = ["name",
                       "body",
                       "priority",
                       "date",
                       "expired",
                       InlineLink("roles",
                                  label = T("Roles"),
                                  field = "group_id",
                                  ),
                       ]
        list_fields = ["date",
                       "priority",
                       "name",
                       "body",
                       "post_role.group_id",
                       "expired",
                       ]
        orderby = "cms_post.date desc"
    else:
        crud_fields = ["name",
                       "body",
                       "date",
                       InlineComponent("document",
                                       name = "file",
                                       label = T("Attachments"),
                                       fields = ["file", "comments"],
                                       filterby = {"field": "file",
                                                   "options": "",
                                                   "invert": True,
                                                   },
                                       ),
                       "comments",
                       ]
        list_fields = ["post_module.module",
                       "post_module.resource",
                       "name",
                       "date",
                       "comments",
                       ]
        orderby = "cms_post.name"

    s3db.configure("cms_post",
                   crud_form = CustomForm(*crud_fields),
                   list_fields = list_fields,
                   orderby = orderby,
                   )

# -----------------------------------------------------------------------------
def cms_post_controller(**attr):

    s3 = current.response.s3

    # Custom prep
    standard_prep = s3.prep
    def prep(r):
        # Call standard prep
        result = standard_prep(r) if callable(standard_prep) else True

        table = r.table

        get_vars = r.get_vars
        module, context = get_vars.get("module"), get_vars.get("resource")

        if module == "default":
            if context == "Contact":
                page, name = "contact", "Contact Information"
            elif context == "Privacy":
                page, name = "privacy", "Privacy Notice"
            elif context == "Legal":
                page, name = "legal", "Legal Notice"
            else:
                page, name = None, None
            if page and name:
                url = URL(c="default", f="index", args=[page])
                r.resource.configure(create_next=url, update_next=url)
                table.name.default = name


        return result
    s3.prep = prep

    return attr

# END =========================================================================
