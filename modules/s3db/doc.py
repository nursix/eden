"""
    Document Library

    Copyright: 2011-2022 (c) Sahana Software Foundation

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

__all__ = ("DocumentEntityModel",
           "DocumentModel",
           "DocumentTagModel",
           "DocumentCKEditorModel",
           "DocumentDataCardModel",
           "doc_rheader",
           "doc_document_list_layout",
           )

import os

from io import BytesIO
from uuid import uuid4

from gluon import *
from gluon.storage import Storage

from ..core import *

# =============================================================================
class DocumentEntityModel(DataModel):

    names = ("doc_entity",
             )

    def model(self):

        T = current.T

        # ---------------------------------------------------------------------
        # Document-referencing entities
        #
        entity_types = {"act_activity": T("Activity"),
                        "asset_asset": T("Asset"),
                        "cap_resource": T("CAP Resource"),
                        "cms_post": T("Post"),
                        "cr_shelter": T("Shelter"),
                        "deploy_mission": T("Mission"),
                        "dvr_case": T("Case"),
                        "dvr_case_activity": T("Case Activity"),
                        "event_event": T("Event"),
                        "event_incident": T("Incident"),
                        "event_incident_report": T("Incident Report"),
                        "event_scenario": T("Scenario"),
                        "event_sitrep": T("Situation Report"),
                        "fin_expense": T("Expense"),
                        "fire_station": T("Fire Station"),
                        "hms_hospital": T("Hospital"),
                        "hrm_human_resource": T("Staff Record"),
                        "hrm_training_event_report": T("Training Event Report"),
                        "inv_adj": T("Stock Adjustment"),
                        "inv_recv": T("Incoming Shipment"),
                        "inv_send": T("Sent Shipment"),
                        "inv_warehouse": T("Warehouse"),
                        "med_patient": T("Patient"),
                        "pr_group": T("Group"),
                        "project_project": T("Project"),
                        "project_activity": T("Project Activity"),
                        "project_task": T("Task"),
                        "org_facility": T("Facility"),
                        "org_group": T("Organization Group"),
                        "org_office": T("Office"),
                        "req_need": T("Need"),
                        "req_req": T("Request"),
                        "security_seized_item": T("Seized Item"),
                        }

        tablename = "doc_entity"
        self.super_entity(tablename, "doc_id", entity_types)

        # Components
        self.add_components(tablename,
                            doc_document = "doc_id",
                            doc_image = "doc_id",
                            )

# =============================================================================
class DocumentModel(DataModel):
    """
        Model for uploaded documents and images
    """

    names = ("doc_document",
             "doc_document_id",
             "doc_image",
             )

    def model(self):

        T = current.T
        db = current.db
        folder = current.request.folder
        s3 = current.response.s3
        crud_strings = s3.crud_strings

        person_id = self.pr_person_id
        location_id = self.gis_location_id
        organisation_id = self.org_organisation_id

        # Shortcuts
        configure = self.configure
        define_table = self.define_table
        super_link = self.super_link

        # ---------------------------------------------------------------------
        # Default document status
        #
        doc_status = {"NEW": T("New")}

        # ---------------------------------------------------------------------
        # Documents
        #
        tablename = "doc_document"
        define_table(tablename,
                     # Instance
                     super_link("source_id", "stats_source"),
                     # Component not instance
                     super_link("doc_id", "doc_entity"),
                     Field("name", length=128,
                           # Allow Name to be added onvalidation
                           requires = IS_LENGTH(128),
                           label = T("Name")
                           ),
                     Field("file", "upload",
                           label = T("File"),
                           autodelete = True,
                           length = current.MAX_FILENAME_LENGTH,
                           represent = self.doc_file_represent,
                           # upload folder needs to be visible to the
                           # download() function as well as the upload
                           uploadfolder = os.path.join(folder, "uploads"),
                           ),
                     Field("mime_type",
                           readable = False,
                           writable = False,
                           ),
                     Field("url",
                           label = T("URL"),
                           represent = s3_url_represent,
                           requires = IS_EMPTY_OR(IS_URL(allowed_schemes = ["http", "https", None],
                                                         prepend_scheme = "http",
                                                         )),
                           ),

                     DateField(label = T("Date Published"),
                               default = "now",
                               ),
                     person_id(
                        # Enable when-required
                        label = T("Author"),
                        readable = False,
                        writable = False,
                        comment = self.pr_person_comment(T("Author"),
                                                         T("The Author of this Document (optional)"),
                                                         ),
                        ),

                     # Status-field for advanced document management,
                     # enable+configure in template as/when required
                     Field("status",
                           default = "NEW",
                           #represent = represent_option(doc_status),
                           requires = IS_IN_SET(doc_status, zero=None),
                           readable = False,
                           writable = False,
                           ),
                     # Mailmerge template?
                     Field("is_template", "boolean",
                           default = False,
                           readable = False,
                           writable = False,
                           ),

                     # Context links, enable+configure in template
                     # as/when required (TODO should be many-to-many?)
                     organisation_id(readable = False,
                                     writable = False,
                                     ),
                     super_link("site_id", "org_site",
                                readable = False,
                                writable = False,
                                ),
                     location_id(readable = False,
                                 writable = False,
                                 ),

                     CommentsField(),
                     Field("checksum",
                           readable = False,
                           writable = False,
                           ),
                     )

        # CRUD Strings
        crud_strings[tablename] = Storage(
            label_create = T("Add Reference Document"),
            title_display = T("Document Details"),
            title_list = T("Documents"),
            title_update = T("Edit Document"),
            label_list_button = T("List Documents"),
            label_delete_button = T("Delete Document"),
            msg_record_created = T("Document added"),
            msg_record_modified = T("Document updated"),
            msg_record_deleted = T("Document deleted"),
            msg_list_empty = T("No Documents found"),
            )

        # Filter Widgets
        # - define in-template if-required

        # Resource Configuration
        configure(tablename,
                  context = {"organisation": "organisation_id",
                             "person": "person_id",
                             "site": "site_id",
                             },
                  deduplicate = self.document_duplicate,
                  list_layout = doc_document_list_layout, # TODO remove?
                  onvalidation = self.document_onvalidation,
                  super_entity = "stats_source",
                  )

        # Foreign Key Template (e.g. for link tables)
        represent = doc_DocumentRepresent(lookup = tablename,
                                          fields = ("name", "file", "url"),
                                          labels = "%(name)s",
                                          show_link = True)

        document_id = FieldTemplate("document_id", "reference %s" % tablename,
                                    label = T("Document"),
                                    ondelete = "CASCADE",
                                    represent = represent,
                                    requires = IS_ONE_OF(db,
                                                         "doc_document.id",
                                                         represent,
                                                         ),
                                    )

        self.add_components(tablename,
                            doc_document_tag = document_id,
                            msg_attachment = document_id,
                            )

        # ---------------------------------------------------------------------
        # Images
        #
        doc_image_type_opts = {1:  T("Photograph"),
                               2:  T("Map"),
                               3:  T("Document Scan"),
                               99: T("other")
                               }

        tablename = "doc_image"
        define_table(tablename,
                     # Component not instance
                     super_link("doc_id", "doc_entity"),
                     Field("name", length=128,
                           label = T("Name"),
                           # Allow Name to be added onvalidation
                           requires = IS_LENGTH(128),
                           ),
                     Field("type", "integer",
                           default = 1,
                           label = T("Image Type"),
                           represent = represent_option(doc_image_type_opts),
                           requires = IS_IN_SET(doc_image_type_opts,
                                                zero=None),
                           ),
                     Field("file", "upload",
                           autodelete = True,
                           label = T("File"),
                           length = current.MAX_FILENAME_LENGTH,
                           represent = represent_image(),
                           requires = IS_EMPTY_OR(
                                        IS_IMAGE(extensions = (s3.IMAGE_EXTENSIONS)),
                                        # Distinguish from prepop
                                        null = "",
                                        ),
                           # upload folder needs to be visible to the
                           # download() function as well as the upload
                           uploadfolder = os.path.join(folder, "uploads", "images"),
                           widget = S3ImageCropWidget((600, 600)),
                           ),
                     Field("mime_type",
                           readable = False,
                           writable = False,
                           ),
                     Field("url",
                           label = T("URL"),
                           represent = s3_url_represent,
                           requires = IS_EMPTY_OR(IS_URL()),
                           ),

                     DateField(label = T("Date Taken"),
                               ),
                     person_id(label = T("Author"),
                               ),

                     # Context links, enable+configure in template
                     # as/when required (TODO should be many-to-many?)
                     organisation_id(readable = False,
                                     writable = False,
                                     ),
                     super_link("site_id", "org_site",
                                readable = False,
                                writable = False,
                                ),
                     location_id(readable = False,
                                 writable = False,
                                 ),
                     super_link("pe_id", "pr_pentity",
                                readable = False,
                                writable = False,
                                ),

                     CommentsField(),
                     Field("checksum",
                           readable = False,
                           writable = False,
                           ),
                     )

        # CRUD Strings
        crud_strings[tablename] = Storage(
            label_create = T("Add Photo"),
            title_display = T("Photo Details"),
            title_list = T("Photos"),
            title_update = T("Edit Photo"),
            label_list_button = T("List Photos"),
            label_delete_button = T("Delete Photo"),
            msg_record_created = T("Photo added"),
            msg_record_modified = T("Photo updated"),
            msg_record_deleted = T("Photo deleted"),
            msg_list_empty = T("No Photos found"),
            )

        # Resource Configuration
        configure(tablename,
                  deduplicate = self.document_duplicate,
                  onvalidation = lambda form: \
                                 self.document_onvalidation(form, document=False)
                  )

        # ---------------------------------------------------------------------
        # Pass model-global names to response.s3
        #
        return {"doc_document_id": document_id,
                }

    # -------------------------------------------------------------------------
    def defaults(self):
        """ Safe defaults if the module is disabled """

        return {"doc_document_id": FieldTemplate.dummy("document_id"),
                }

    # -------------------------------------------------------------------------
    @staticmethod
    def doc_file_represent(filename):
        """
            File representation

            Args:
                filename: the stored file name (field value)

            Returns:
                a link to download the file
        """

        if filename:
            try:
                # Check whether file exists and extract the original
                # file name from the stored file name
                origname = current.db.doc_document.file.retrieve(filename)[0]
            except IOError:
                return current.T("File not found")
            else:
                return A(origname,
                         _href=URL(c = "default",
                                   f = "download",
                                   args = [filename],
                                   vars = {"otn": "doc_document"},
                                   ),
                         )
        else:
            return current.messages["NONE"]

    # -------------------------------------------------------------------------
    @staticmethod
    def document_duplicate(item):
        """ Import item de-duplication """

        data = item.data
        query = None
        filename = data.get("file")
        if filename:
            table = item.table
            query = (table.file == filename)
        else:
            url = data.get("url")
            if url:
                table = item.table
                query = (table.url == url)

        if query:
            duplicate = current.db(query).select(table.id,
                                                 limitby=(0, 1)).first()

            if duplicate:
                item.id = duplicate.id
                item.method = item.METHOD.UPDATE

    # -------------------------------------------------------------------------
    @staticmethod
    def document_onvalidation(form, document=True):
        """ Form validation for both, documents and images """
        # TODO separate image/document

        form_vars = form.vars
        doc = form_vars.file

        if doc is None:
            # If this is a prepop, then file not in form
            # Interactive forms with empty doc has this as "" not None
            return

        if not document:
            encoded_file = form_vars.get("imagecrop-data", None)
            if encoded_file:
                # S3ImageCropWidget
                import base64
                metadata, encoded_file = encoded_file.split(",")
                #filename, datatype, enctype = metadata.split(";")
                filename = metadata.split(";", 1)[0]
                f = Storage()
                f.filename = uuid4().hex + filename
                f.file = BytesIO(base64.b64decode(encoded_file))
                doc = form_vars.file = f
                if not form_vars.name:
                    form_vars.name = filename

        if not hasattr(doc, "file"):
            # Record update without new file upload => keep existing
            record_id = current.request.post_vars.id
            if record_id:
                db = current.db
                if document:
                    tablename = "doc_document"
                else:
                    tablename = "doc_image"
                table = db[tablename]
                record = db(table.id == record_id).select(table.file,
                                                          limitby = (0, 1),
                                                          ).first()
                if record:
                    doc = record.file

        if not hasattr(doc, "file") and not doc and not form_vars.url:
            if document:
                msg = current.T("Either file upload or document URL required.")
            else:
                msg = current.T("Either file upload or image URL required.")
            if "file" in form_vars:
                form.errors.file = msg
            if "url" in form_vars:
                form.errors.url = msg

        if hasattr(doc, "file"):
            name = form_vars.name
            if not name:
                # Use filename as document/image title
                form_vars.name = doc.filename

        # Do a checksum on the file to see if it's a duplicate
        #is_upload = hasattr(doc, "file") and hasattr(doc, "filename")
        #if is_upload and doc.filename:
        #    f = doc.file
        #    form_vars.checksum = doc_checksum(f.read())
        #    f.seek(0)
        #    if not form_vars.name:
        #        form_vars.name = doc.filename

        #if form_vars.checksum is not None:
        #    # Duplicate allowed if original version is deleted
        #    query = ((table.checksum == form_vars.checksum) & \
        #             (table.deleted == False))
        #    result = db(query).select(table.name,
        #                              limitby=(0, 1)).first()
        #    if result:
        #        doc_name = result.name
        #        form.errors["file"] = "%s %s" % \
        #                              (T("This file already exists on the server as"), doc_name)

# =============================================================================
class DocumentTagModel(DataModel):
    """
        Document Tags
    """

    names = ("doc_document_tag",)

    def model(self):

        T = current.T

        # ---------------------------------------------------------------------
        # Document Tags
        # - Key-Value extensions
        # - can be used to provide conversions to external systems
        # - can be a Triple Store for Semantic Web support
        # - can be used to add a document type
        # - can be used to add custom fields
        #
        tablename = "doc_document_tag"
        self.define_table(tablename,
                          self.doc_document_id(),
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
                       deduplicate = S3Duplicate(primary = ("document_id",
                                                            "tag",
                                                            ),
                                                 ),
                       )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        #return {}

# =============================================================================
def doc_rheader(r, tabs=None):
    """ DOC resource headers """

    if r.representation != "html":
        # Resource headers only used in interactive views
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

        if tablename == "doc_document":
            if not tabs:
                tabs = [(T("Basic Details"), None),
                        ]
            rheader_fields = [["organisation_id", "file"],
                              ["person_id", "url"],
                              ["date"],
                              ]
            rheader_title = "name"

            rheader = S3ResourceHeader(rheader_fields, tabs, title=rheader_title)
            rheader = rheader(r, table=resource.table, record=record)

        elif tablename == "doc_image":
            if not tabs:
                tabs = [(T("Basic Details"), None),
                        ]
            rheader_fields = [["type"],
                              ["date"],
                              ]
            rheader_title = "name"

        else:
            return None

        rheader = S3ResourceHeader(rheader_fields, tabs, title=rheader_title)
        rheader = rheader(r, table=resource.table, record=record)

    return rheader

# =============================================================================
def doc_checksum(docstr):
    """ Calculate a checksum for a file """

    import hashlib

    converted = hashlib.sha1(docstr).hexdigest()
    return converted

# =============================================================================
def doc_document_list_layout(list_id, item_id, resource, rfields, record):
    """
        Default dataList item renderer for Documents, e.g. on the HRM Profile

        NB The CSS classes here refer to static/themes/bootstrap/cards.css & newsfeed.css
        - so this CSS either needs moving to core or else this needs modifying for default CSS

        Args:
            list_id: the HTML ID of the list
            item_id: the HTML ID of the item
            resource: the CRUDResource to render
            rfields: the S3ResourceFields to render
            record: the record as dict

        TODO remove?
    """

    record_id = record["doc_document.id"]
    item_class = "thumbnail"

    raw = record._row
    title = record["doc_document.name"]
    filename = raw["doc_document.file"] or ""
    url = raw["doc_document.url"] or ""
    comments = raw["doc_document.comments"] or ""

    if filename:
        try:
            # Check whether file exists and extract the original
            # file name from the stored file name
            origname = current.s3db.doc_document.file.retrieve(filename)[0]
        except (IOError, TypeError):
            origname = current.messages["NONE"]
        doc_url = URL(c="default", f="download", args=[filename])
        body = P(ICON("attachment"),
                 " ",
                 SPAN(A(origname,
                        _href=doc_url,
                        )
                      ),
                 " ",
                 _class="card_1_line",
                 )
    elif url:
        body = P(ICON("link"),
                 " ",
                 SPAN(A(url,
                        _href=url,
                        )),
                 " ",
                 _class="card_1_line",
                 )
    else:
        # Shouldn't happen!
        body = P(_class="card_1_line")

    # Edit Bar
    permit = current.auth.s3_has_permission
    table = current.s3db.doc_document
    if permit("update", table, record_id=record_id):
        edit_btn = A(ICON("edit"),
                     _href=URL(c="doc", f="document",
                               args=[record_id, "update.popup"],
                               vars={"refresh": list_id,
                                     "record": record_id}),
                     _class="s3_modal",
                     _title=current.T("Edit Document"),
                     )
    else:
        edit_btn = ""
    if permit("delete", table, record_id=record_id):
        delete_btn = A(ICON("delete"),
                       _class="dl-item-delete",
                       )
    else:
        delete_btn = ""
    edit_bar = DIV(edit_btn,
                   delete_btn,
                   _class="edit-bar fright",
                   )

    # Render the item
    item = DIV(DIV(ICON("icon"),
                   SPAN(" %s" % title,
                        _class="card-title"),
                   edit_bar,
                   _class="card-header",
                   ),
               DIV(DIV(DIV(body,
                           P(SPAN(comments),
                             " ",
                             _class="card_manylines",
                             ),
                           _class="media",
                           ),
                       _class="media-body",
                       ),
                   _class="media",
                   ),
               _class=item_class,
               _id=item_id,
               )

    return item

# =============================================================================
class doc_DocumentRepresent(S3Represent):
    """ Representation of Documents """

    def link(self, k, v, row=None):
        """
            Represent a (key, value) as hypertext link.

            Args:
                k: the key (doc_document.id)
                v: the representation of the key
                row: the row with this key
        """

        if row:
            try:
                filename = row["doc_document.file"]
                url = row["doc_document.url"]
            except AttributeError:
                return v
            else:
                if filename:
                    url = URL(c="default", f="download", args=filename)
                    return A(v, _href=url)
                elif url:
                    return A(v, _href=url)
        return v

# =============================================================================
class DocumentCKEditorModel(DataModel):
    """
        Storage for Images used by CKEditor
        - and hence the s3_richtext_widget

        Based on https://github.com/timrichardson/web2py_ckeditor4
    """

    names = ("doc_ckeditor",
             "doc_filetype",
             )

    def model(self):

        #T = current.T

        # ---------------------------------------------------------------------
        # Images
        #
        tablename = "doc_ckeditor"
        self.define_table(tablename,
                          Field("title", length=255),
                          Field("filename", length=255),
                          Field("flength", "integer"),
                          Field("mime_type", length=128),
                          Field("upload", "upload",
                                #uploadfs = self.settings.uploadfs,
                                requires = [IS_NOT_EMPTY(),
                                            IS_LENGTH(maxsize=10485760, # 10 Mb
                                                      minsize=0)],
                                ),
                          )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return {"doc_filetype": self.doc_filetype,
                }

    # -------------------------------------------------------------------------
    @staticmethod
    def doc_filetype(filename):
        """
            Takes a filename and returns a category based on the file type.
            Categories: word, excel, powerpoint, flash, pdf, image, video, audio, archive, other.
        """

        ftype = "other"

        parts = os.path.splitext(filename)
        if len(parts) > 1:
            ext = parts[1][1:].lower()
            if ext in ("png", "jpg", "jpeg", "gif"):
                ftype = "image"
            elif ext in ("avi", "mp4", "m4v", "ogv", "wmv", "mpg", "mpeg"):
                ftype = "video"
            elif ext in ("mp3", "m4a", "wav", "ogg", "aiff"):
                ftype = "audio"
            elif ext in ("zip", "7z", "tar", "gz", "tgz", "bz2", "rar"):
                ftype = "archive"
            elif ext in ("doc", "docx", "dot", "dotx", "rtf"):
                ftype = "word"
            elif ext in ("xls", "xlsx", "xlt", "xltx", "csv"):
                ftype = "excel"
            elif ext in ("ppt", "pptx"):
                ftype = "powerpoint"
            elif ext in ("flv", "swf"):
                ftype = "flash"
            elif ext == "pdf":
                ftype = "pdf"

        return ftype

# =============================================================================
class DocumentDataCardModel(DataModel):
    """
        Model to manage context-specific features of printable
        data cards (PDFCardWriter)
    """

    names = ("doc_card_config",
             "doc_card_types",
             "doc_update_card_type_requires",
             )

    def model(self):

        T = current.T

        #db = current.db
        s3 = current.response.s3

        #define_table = self.define_table
        crud_strings = s3.crud_strings

        # ---------------------------------------------------------------------
        # Card Types
        #
        card_types = {"VOLID": T("Volunteer ID Card"),
                      }

        # ---------------------------------------------------------------------
        # Card Configuration
        #
        uploadfolder = os.path.join(current.request.folder, "uploads", "signatures")

        tablename = "doc_card_config"
        self.define_table(tablename,
                          # Context links (e.g. Organisation):
                          self.org_organisation_id(),
                          # Card Type:
                          Field("card_type",
                                label = T("Card Type"),
                                requires = IS_IN_SET(card_types,
                                                     sort = True,
                                                     zero = None,
                                                     ),
                                represent = represent_option(card_types),
                                ),
                          # Card Feature Configurations:
                          Field("authority_statement", "text",
                                label = T("Authority Statement"),
                                represent = s3_text_represent,
                                widget = s3_comments_widget,
                                ),
                          Field("org_statement", "text",
                                label = T("Organization Statement"),
                                represent = s3_text_represent,
                                widget = s3_comments_widget,
                                ),
                          Field("signature", "upload",
                                label = T("Signature"),
                                autodelete = True,
                                length = current.MAX_FILENAME_LENGTH,
                                represent = represent_image("doc_card_config", "signature"),
                                requires = IS_EMPTY_OR(IS_IMAGE(extensions=(s3.IMAGE_EXTENSIONS)),
                                                       # Distinguish from prepop
                                                       null = "",
                                                       ),
                                uploadfolder = uploadfolder,
                                ),
                          Field("signature_text", "text",
                                label = T("Signature Text"),
                                represent = s3_text_represent,
                                widget = s3_comments_widget,
                                ),
                          Field("validity_period", "integer",
                                default = 12,
                                label = T("Validity Period (Months)"),
                                requires = IS_EMPTY_OR(IS_INT_IN_RANGE(0)),
                                represent = lambda v: (T("%(months)s months") % {"months": v}) if v else "-",
                                ),
                          CommentsField(),
                          )

        # Table configuration
        self.configure(tablename,
                       deduplicate = S3Duplicate(primary=("organisation_id", "card_type"),
                                                 ),
                       )

        # CRUD Strings
        crud_strings[tablename] = Storage(
            label_create = T("Create Card Configuration"),
            title_display = T("Card Configuration Details"),
            title_list = T("Card Configuration"),
            title_update = T("Edit Card Configuration"),
            label_list_button = T("List Card Configurations"),
            label_delete_button = T("Delete Card Configuration"),
            msg_record_created = T("Card Configuration created"),
            msg_record_modified = T("Card Configuration updated"),
            msg_record_deleted = T("Card Configuration deleted"),
            msg_list_empty = T("No Card Configuration currently registered"),
        )

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return {"doc_card_types": card_types,
                "doc_update_card_type_requires": self.update_card_type_requires,
                }

    # -------------------------------------------------------------------------
    def defaults(self):
        """ Safe defaults for names in case the module is disabled """

        return {"doc_card_types": {},
                "doc_update_card_type_requires": self.update_card_type_requires,
                }

    # -------------------------------------------------------------------------
    @staticmethod
    def update_card_type_requires(record_id, organisation_id):
        """
            Make sure each card type can be defined only once per org

            Args:
                record_id: the current doc_card_config record ID
                           (when currently editing a record)
                organisation_id: the organisation record ID
        """

        s3db = current.s3db

        # Find out which card types are already configured for this org
        table = s3db.doc_card_config
        query = (table.organisation_id == organisation_id) & \
                (table.deleted == False)
        rows = current.db(query).select(table.id,
                                        table.card_type,
                                        )
        this = None
        defined = set()
        for row in rows:
            if str(row.id) == str(record_id):
                this = row.card_type
            defined.add(row.card_type)

        # Determine which card types can still be configured
        card_types = {k: v for (k, v) in s3db.doc_card_types.items()
                           if k == this or k not in defined}

        # Limit selection to these card types
        table.card_type.requires = IS_IN_SET(card_types,
                                             sort = True,
                                             zero = None,
                                             )
        if not card_types:
            # No further card types can be configured
            s3db.configure("doc_card_config",
                           insertable = False,
                           )
        elif this and list(card_types.keys()) == [this]:
            # All other types are already configured => can't change this
            table.card_type.writable = False

# END =========================================================================
