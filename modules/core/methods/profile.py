"""
    Profile (Multi-perspective single-record view)

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

__all__ = ("S3Profile",
           )

from uuid import uuid4

from gluon import current, redirect
from gluon.html import *
from gluon.storage import Storage

from ..resource import FS
from ..tools import get_crud_string, s3_str
from ..ui import ICON

from .crud import BasicCRUD
from .report import S3Report

# =============================================================================
class S3Profile(BasicCRUD):
    """
        Interactive Method Handler for Profile Pages

        Configure widgets using s3db.configure(tablename, profile_widgets=[])

        TODO Make more configurable:
             - Currently uses internal widgets rather than CRUDMethod widgets

        TODO unify datalist and datatable methods with the superclass
             methods (requires re-design of the superclass methods)
        TODO allow as default handler for interactive single-record-no-method
             GET requests (include read/update from superclass)
    """

    # -------------------------------------------------------------------------
    def apply_method(self, r, **attr):
        """
            API entry point

            Args:
                r: the CRUDRequest instance
                attr: controller attributes for the request
        """

        if r.http in ("GET", "POST", "DELETE"):
            if r.record:
                # Initialize CRUD form
                self.settings = current.response.s3.crud
                self.form = form = self.resource.get_config("crud_form")
                if not form:
                    from ..ui import DefaultForm
                    self.form = DefaultForm()

                # Render page
                output = self.profile(r, **attr)
                return output

            elif r.representation not in ("dl", "aadata"):
                # Redirect to the List View
                redirect(r.url(method=""))

            else:
                # No point redirecting
                r.error(404, current.ERROR.BAD_RECORD)
        else:
            r.error(405, current.ERROR.BAD_METHOD)

    # -------------------------------------------------------------------------
    def profile(self, r, **attr):
        """
            Generate a Profile page

            Args:
                r: the CRUDRequest instance
                attr: controller attributes for the request
        """

        tablename = self.tablename
        get_config = current.s3db.get_config

        header = get_config(tablename, "profile_header")

        # Get the page widgets
        widgets = get_config(tablename, "profile_widgets")
        if not widgets and not header:
            # Profile page not configured:
            if r.representation not in ("dl", "aadata"):
                # Redirect to the Read View
                redirect(r.url(method="read"))
            else:
                # No point redirecting
                r.error(405, current.ERROR.BAD_METHOD)

        # Index the widgets by their position in the config
        for index, widget in enumerate(widgets):
            widget["index"] = index

        if r.representation == "dl":
            # Ajax-update of one datalist
            index = r.get_vars.get("update", None)
            if index:
                try:
                    index = int(index)
                except ValueError:
                    datalist = ""
                else:
                    # @ToDo: Check permissions to the Resource & do
                    # something different if no permission
                    datalist = self._datalist(r, widgets[index], **attr)
            output = {"item": datalist}

        elif r.representation == "aadata":
            # Ajax-update of one datatable
            index = r.get_vars.get("update", None)
            if index:
                try:
                    index = int(index)
                except ValueError:
                    datalist = ""
                else:
                    # @ToDo: Check permissions to the Resource & do
                    # something different if no permission
                    datatable = self._datatable(r, widgets[index], **attr)
            return datatable

        else:
            # Default page-load

            # Page Title
            title = get_config(tablename, "profile_title")
            if not title:
                try:
                    title = r.record.name
                except:
                    title = current.T("Profile Page")
            elif callable(title):
                title = title(r)

            # Page Header
            if not header:
                header = H2(title, _class="profile-header")
            elif callable(header):
                header = header(r)

            output = {"title": title,
                      "header": header,
                      }

            # Update Form, if configured
            update = get_config(tablename, "profile_update")
            if update:
                editable = get_config(tablename, "editable", True)
                authorised = self._permitted(method="update")
                if authorised and editable:
                    show = get_crud_string(tablename, "title_update")
                    hide = current.T("Hide Form")
                    form = self.update(r, **attr)["form"]
                else:
                    show = get_crud_string(tablename, "title_display")
                    hide = current.T("Hide Details")
                    form = self.read(r, **attr)["item"]

                if update == "visible":
                    hidden = False
                    label = hide
                    style_hide, style_show = None, "display:none"
                else:
                    hidden = True
                    label = show
                    style_hide, style_show = "display:none", None

                toggle = A(SPAN(label,
                                data = {"on": show,
                                        "off": hide,
                                        },
                                ),
                           ICON("down", _style=style_show),
                           ICON("up", _style=style_hide),
                           data = {"hidden": hidden},
                           _class = "form-toggle action-lnk",
                           )
                form.update(_style=style_hide)
                output["form"] = DIV(toggle,
                                     form,
                                     _class = "profile-update",
                                     )
            else:
                output["form"] = ""

            # Widgets
            response = current.response
            rows = []
            append = rows.append
            row = None
            cols = get_config(tablename, "profile_cols")
            if not cols:
                cols = 2
            row_cols = 0
            for widget in widgets:

                # Render the widget
                w_type = widget["type"]
                if w_type == "comments":
                    w = self._comments(r, widget, **attr)
                elif w_type == "datalist":
                    w = self._datalist(r, widget, **attr)
                elif w_type == "datatable":
                    w = self._datatable(r, widget, **attr)
                elif w_type == "form":
                    w = self._form(r, widget, **attr)
                elif w_type == "map":
                    w = self._map(r, widget, widgets, **attr)
                elif w_type == "report":
                    w = self._report(r, widget, **attr)
                elif w_type == "organizer":
                    w = self._organizer(r, widget, **attr)
                elif w_type == "custom":
                    w = self._custom(r, widget, **attr)
                else:
                    if response.s3.debug:
                        raise SyntaxError("Unsupported widget type %s" %
                                          w_type)
                    else:
                        # ignore
                        continue

                if row is None:
                    # Start new row
                    row = DIV(_class="row profile")
                    row_cols = 0

                # Append widget to row
                row.append(w)
                colspan = widget.get("colspan", 1)
                row_cols += colspan
                if row_cols == cols:
                    # Close this row
                    append(row)
                    row = None

            if row:
                # We have an incomplete row of widgets
                append(row)
            output["rows"] = rows

            # Activate this if a project needs it
            #response.view = get_config(tablename, "profile_view") or \
            #                self._view(r, "profile.html")
            response.view = self._view(r, "profile.html")

        return output

    # -------------------------------------------------------------------------
    @staticmethod
    def _resolve_context(r, tablename, context):
        """
            Resolve a context filter

            Args:
                context: the context (as a string)
                id: the record_id
        """

        record_id = r.id
        if not record_id:
            return None

        if not context:
            query = None

        elif type(context) is tuple:
            context, field = context
            query = (FS(context) == r.record[field])

        elif context == "location":
            # Show records linked to this Location & all it's Child Locations
            s = "(location)$path"
            # This version doesn't serialize_url
            #m = ("%(id)s/*,*/%(id)s/*" % dict(id=id)).split(",")
            #filter = (FS(s).like(m)) | (FS(s) == id)
            m = ("%(id)s,%(id)s/*,*/%(id)s/*,*/%(id)s" % dict(id=record_id)).split(",")
            m = [f.replace("*", "%") for f in m]
            query = (FS(s).like(m))
        # @ToDo:
        #elif context == "organisation":
        #    # Show records linked to this Organisation and all it's Branches
        #    s = "(%s)" % context
        #    query = (FS(s) == id)
        else:
            # Normal: show just records linked directly to this master resource
            s = "(%s)" % context
            query = (FS(s) == record_id)

        # Define target resource
        resource = current.s3db.resource(tablename, filter=query)
        r.customise_resource(tablename)
        return resource, query

    # -------------------------------------------------------------------------
    def _comments(self, r, widget, **attr):
        """
            Generate a Comments widget

            Args:
                r: the CRUDRequest instance
                widget: the widget definition as dict
                attr: controller attributes for the request

            TODO Configurable to use either Disqus or internal Comments
        """

        label = widget.get("label", "")
        # Activate if-required
        #if label and isinstance(label, str):
        if label:
            label = current.T(label)
        icon = widget.get("icon", "")
        if icon:
            icon = ICON(icon)

        _class = self._lookup_class(r, widget)

        comments = "@ToDo"

        # Render the widget
        output = DIV(H4(icon,
                        label,
                        _class = "profile-sub-header",
                        ),
                     DIV(comments,
                         _class = "card-holder",
                         ),
                     _class = _class,
                     )

        return output

    # -------------------------------------------------------------------------
    def _custom(self, r, widget, **attr):
        """
            Generate a Custom widget

            Args:
                r: the CRUDRequest instance
                widget: the widget definition as dict
                attr: controller attributes for the request
        """

        label = widget.get("label", "")
        # Activate if-required
        #if label and isinstance(label, str):
        if label:
            label = current.T(label)
        icon = widget.get("icon", "")
        if icon:
            icon = ICON(icon)

        _class = self._lookup_class(r, widget)

        contents = widget["fn"](r, **attr)

        # Render the widget
        output = DIV(H4(icon,
                        label,
                        _class = "profile-sub-header",
                        ),
                     DIV(contents,
                         _class = "card-holder",
                         ),
                     _class = _class,
                     )

        return output

    # -------------------------------------------------------------------------
    def _datalist(self, r, widget, **attr):
        """
            Generate a data list

            Args:
                r: the CRUDRequest instance
                widget: the widget definition as dict
                attr: controller attributes for the request
        """

        T = current.T

        widget_get = widget.get

        context = widget_get("context")
        tablename = widget_get("tablename")
        resource, context = self._resolve_context(r, tablename, context)

        # Config Options:
        # 1st choice: Widget
        # 2nd choice: get_config
        # 3rd choice: Default
        config = resource.get_config
        list_fields = widget_get("list_fields",
                                 config("list_fields", None))
        list_layout = widget_get("list_layout",
                                 config("list_layout", None))
        orderby = widget_get("orderby",
                             config("list_orderby",
                                    config("orderby",
                                           ~resource.table.created_on)))

        widget_filter = widget_get("filter")
        if widget_filter:
            resource.add_filter(widget_filter)

        # Use the widget-index to create a unique ID
        list_id = "profile-list-%s-%s" % (tablename, widget["index"])

        # Page size
        pagesize = widget_get("pagesize", 4)
        representation = r.representation
        if representation == "dl":
            # Ajax-update
            get_vars = r.get_vars
            record_id = get_vars.get("record", None)
            if record_id is not None:
                # Ajax-update of a single record
                resource.add_filter(FS("id") == record_id)
                start, limit = 0, 1
            else:
                # Ajax-update of full page
                start = get_vars.get("start", None)
                limit = get_vars.get("limit", None)
                if limit is not None:
                    try:
                        start = int(start)
                        limit = int(limit)
                    except ValueError:
                        start, limit = 0, pagesize
                else:
                    start = None
        else:
            # Page-load
            start, limit = 0, pagesize

        # Ajax-delete items?
        if representation == "dl" and r.http in ("DELETE", "POST"):
            if "delete" in r.get_vars:
                return self._dl_ajax_delete(r, resource)
            else:
                r.error(405, current.ERROR.BAD_METHOD)

        # dataList
        datalist, numrows = resource.datalist(fields = list_fields,
                                              start = start,
                                              limit = limit,
                                              list_id = list_id,
                                              orderby = orderby,
                                              layout = list_layout,
                                              )
        # Render the list
        ajaxurl = r.url(vars={"update": widget["index"]},
                        representation="dl")
        data = datalist.html(ajaxurl = ajaxurl,
                             pagesize = pagesize,
                             empty = P(ICON("folder-open-alt"),
                                       BR(),
                                       get_crud_string(tablename,
                                                       "msg_no_match"),
                                       _class = "empty_card-holder"
                                       ),
                             )

        if representation == "dl":
            # This is an Ajax-request, so we don't need the wrapper
            current.response.view = "plain.html"
            return data

        # Interactive only below here
        label = widget_get("label", "")
        # Activate if-required
        #if label and isinstance(label, str):
        if label:
            label = T(label)
        icon = widget_get("icon", "")
        if icon:
            icon = ICON(icon)

        if pagesize and numrows > pagesize:
            # Button to display the rest of the records in a Modal
            more = numrows - pagesize
            get_vars_new = {}
            if context:
                filters = context.serialize_url(resource)
                for f in filters:
                    get_vars_new[f] = filters[f]
            if widget_filter:
                filters = widget_filter.serialize_url(resource)
                for f in filters:
                    get_vars_new[f] = filters[f]
            c, f = tablename.split("_", 1)
            f = widget_get("function", f)
            url = URL(c=c, f=f, args=["datalist.popup"],
                      vars=get_vars_new)
            more = DIV(A(BUTTON("%s (%s)" % (T("see more"), more),
                                _class = "btn btn-mini tiny button",
                                _type = "button",
                                ),
                         _class = "s3_modal",
                         _href = url,
                         _title = label,
                         ),
                       _class = "more_profile",
                       )
        else:
            more = ""

        # Link for create-popup
        create_popup = self._create_popup(r,
                                          widget,
                                          list_id,
                                          resource,
                                          context,
                                          numrows)

        _class = self._lookup_class(r, widget)

        # Render the widget
        output = DIV(create_popup,
                     H4(icon,
                        label,
                        _class = "profile-sub-header",
                        ),
                     DIV(data,
                         more,
                         _class = "card-holder",
                         ),
                     _class = _class,
                     )

        return output

    # -------------------------------------------------------------------------
    def _datatable(self, r, widget, **attr):
        """
            Generate a data table.

            Args:
                r: the CRUDRequest instance
                widget: the widget definition as dict
                attr: controller attributes for the request

            TODO fix export formats
        """

        widget_get = widget.get

        # Parse context
        context = widget_get("context")
        tablename = widget_get("tablename")
        resource, context = self._resolve_context(r, tablename, context)

        # List fields
        list_fields = widget_get("list_fields")
        if not list_fields:
            # @ToDo: Set the parent so that the fkey gets removed from the list_fields
            #resource.parent = s3db.resource("")
            list_fields = resource.list_fields()

        # Widget filter option
        widget_filter = widget_get("filter")
        if widget_filter:
            resource.add_filter(widget_filter)

        # Use the widget-index to create a unique ID
        list_id = "profile-list-%s-%s" % (tablename, widget["index"])

        # Default ORDERBY
        # - first field actually in this table
        def default_orderby():
            for f in list_fields:
                selector = f[1] if isinstance(f, tuple) else f
                if selector == "id":
                    continue
                rfield = resource.resolve_selector(selector)
                if rfield.field:
                    return rfield.field
            return None

        # Pagination
        representation = r.representation
        get_vars = self.request.get_vars
        if representation == "aadata":
            start = get_vars.get("displayStart", None)
            limit = get_vars.get("pageLength", 0)
        else:
            start = get_vars.get("start", None)
            limit = get_vars.get("limit", 0)
        if limit:
            if limit.lower() == "none":
                limit = None
            else:
                try:
                    start = int(start)
                    limit = int(limit)
                except (ValueError, TypeError):
                    start = None
                    limit = 0 # use default
        else:
            # Use defaults
            start = None

        dtargs = attr.get("dtargs", {})

        if r.interactive:
            s3 = current.response.s3

            # How many records per page?
            display_length = widget_get("pagesize", 10)
            dtargs["dt_lengthMenu"] = [[10, 25, 50, -1],
                                       [10, 25, 50, s3_str(current.T("All"))]
                                       ]

            # ORDERBY fallbacks: widget->resource->default
            orderby = widget_get("orderby")
            if not orderby:
                orderby = resource.get_config("orderby")
            if not orderby:
                orderby = default_orderby()

            # Server-side pagination?
            if not s3.no_sspag:
                dt_pagination = True
                if not limit and display_length is not None:
                    limit = 2 * display_length
                else:
                    limit = None
            else:
                dt_pagination = False

            # Get the data table
            dt, totalrows = resource.datatable(fields = list_fields,
                                               start = start,
                                               limit = limit,
                                               orderby = orderby,
                                               list_id = list_id,
                                               )
            displayrows = totalrows

            empty_str = get_crud_string(tablename, "msg_no_match")
            empty = DIV(empty_str, _class="empty")

            dtargs["dt_searching"] = widget_get("dt_searching", True)
            dtargs["dt_pagination"] = dt_pagination
            dtargs["dt_pageLength"] = display_length
            # @todo: fix base URL (make configurable?) to fix export options
            s3.no_formats = True
            dtargs["dt_base_url"] = r.url(method="", vars={})
            get_vars.update(update = widget["index"])
            dtargs["dt_ajax_url"] = r.url(vars=get_vars, representation="aadata")

            actions = widget_get("actions")
            if callable(actions):
                actions = actions(r, list_id)
            if actions:
                dtargs["dt_row_actions"] = actions

            datatable = dt.html(totalrows, displayrows, **dtargs)
            if dt.data:
                empty.update(_style = "display:none")
            else:
                datatable.update(_style = "display:none")
            contents = DIV(datatable, empty, _class="dt-contents")

            # Link for create-popup
            create_popup = self._create_popup(r,
                                              widget,
                                              list_id,
                                              resource,
                                              context,
                                              totalrows)

            # Card holder label and icon
            label = widget_get("label", "")
            # Activate if-required
            #if label and isinstance(label, str):
            if label:
                label = current.T(label)
            else:
                label = get_crud_string(tablename, "title_list")
            icon = widget_get("icon", "")
            if icon:
                icon = ICON(icon)

            _class = self._lookup_class(r, widget)

            # Render the widget
            output = DIV(create_popup,
                         H4(icon,
                            label,
                            _class = "profile-sub-header",
                            ),
                         DIV(contents,
                             _class = "card-holder",
                             ),
                         _class = _class,
                         )

            return output

        elif representation == "aadata":

            # Parse datatable filter/sort query
            searchq, orderby, left = resource.datatable_filter(list_fields,
                                                               get_vars)

            # ORDERBY fallbacks - datatable->widget->resource->default
            if not orderby:
                orderby = widget_get("orderby")
            if not orderby:
                orderby = resource.get_config("orderby")
            if not orderby:
                orderby = default_orderby()

            # DataTable filtering
            if searchq is not None:
                totalrows = resource.count()
                resource.add_filter(searchq)
            else:
                totalrows = None

            # Get the data table
            if totalrows != 0:
                dt, displayrows = resource.datatable(fields = list_fields,
                                                     start = start,
                                                     limit = limit,
                                                     left = left,
                                                     orderby = orderby,
                                                     list_id = list_id,
                                                     )
            else:
                dt, displayrows = None, 0

            if totalrows is None:
                totalrows = displayrows

            # Echo
            draw = int(get_vars.get("draw") or 0)

            # Representation
            if dt is not None:
                data = dt.json(totalrows,
                               displayrows,
                               draw,
                               **dtargs)
            else:
                data = '{"recordsTotal":%s,' \
                       '"recordsFiltered":0,' \
                       '"draw":%s,' \
                       '"data":[]}' % (totalrows, draw)

            return data

        else:
            # Really raise an exception here?
            r.error(415, current.ERROR.BAD_FORMAT)

    # -------------------------------------------------------------------------
    def _form(self, r, widget, **attr):
        """
            Generate a Form widget

            Args:
                r: the CRUDRequest instance
                widget: the widget definition as dict
                attr: controller attributes for the request
        """

        widget_get = widget.get

        label = widget_get("label", "")
        # Activate if-required
        #if label and isinstance(label, str):
        if label:
            label = current.T(label)
        icon = widget_get("icon", "")
        if icon:
            icon = ICON(icon)

        context = widget_get("context", None)
        tablename = widget_get("tablename", None)
        resource, context = self._resolve_context(r, tablename, context)

        # Widget filter option
        widget_filter = widget_get("filter", None)
        if widget_filter:
            resource.add_filter(widget_filter)

        record = resource.select(["id"], limit=1, as_rows=True).first()
        if record:
            record_id = record.id
        else:
            record_id = None

        if record_id:
            readonly = not current.auth.s3_has_permission("update", tablename, record_id)
        else:
            readonly = not current.auth.s3_has_permission("create", tablename)

        crud_form = widget.get("crud_form", None)
        if not crud_form:
            crud_form = resource.get_config("crud_form")
        if not crud_form:
            from ..ui import DefaultForm
            crud_form = DefaultForm()

        get_config = current.s3db.get_config
        if record_id:
            # Update form
            onvalidation = get_config(tablename, "create_onvalidation") or \
                           get_config(tablename, "onvalidation")
            onaccept = get_config(tablename, "create_onaccept") or \
                       get_config(tablename, "onaccept")
        else:
            # Create form
            onvalidation = get_config(tablename, "create_onvalidation") or \
                           get_config(tablename, "onvalidation")
            onaccept = get_config(tablename, "create_onaccept") or \
                       get_config(tablename, "onaccept")

        form = crud_form(request = r,
                         resource = resource,
                         record_id = record_id,
                         readonly = readonly,
                         format = "html",
                         onvalidation = onvalidation,
                         onaccept = onaccept,
                         )
        _class = self._lookup_class(r, widget)

        # Render the widget
        output = DIV(H4(icon,
                        label,
                        _class = "profile-sub-header",
                        ),
                     DIV(form,
                         _class = "form-container thumbnail",
                         ),
                     _class = _class,
                     )

        return output

    # -------------------------------------------------------------------------
    def _map(self, r, widget, widgets, **attr):
        """
            Generate a Map widget

            Args:
                r: the CRUDRequest instance
                widget: the widget definition as dict
                widgets: all widgets (that could be map overlays)
                attr: controller attributes for the request
        """

        T = current.T
        db = current.db
        s3db = current.s3db

        widget_get = widget.get

        label = widget_get("label", "")
        if label and isinstance(label, str):
            label = T(label)
        icon = widget_get("icon", "")
        if icon:
            icon = ICON(icon)

        _class = self._lookup_class(r, widget)

        context = widget_get("context", None)
        # Map widgets have no separate tablename
        tablename = r.tablename
        resource, context = self._resolve_context(r, tablename, context)
        if context:
            cserialize_url = context.serialize_url
        else:
            cserialize_url = lambda res: {}

        height = widget_get("height", 383)
        width = widget_get("width", 568) # span6 * 99.7%
        bbox = widget_get("bbox", {})

        # Default to showing all the resources in datalist widgets as separate layers
        ftable = s3db.gis_layer_feature
        mtable = s3db.gis_marker
        feature_resources = []
        fappend = feature_resources.append
        s3dbresource = s3db.resource
        for overlay in widgets:
            if overlay["type"] not in ("datalist", "datatable", "report"):
                continue
            if not overlay.get("show_on_map", True):
                continue

            # @ToDo: Check permission to access layer (both controller/function & also within Map Config)
            tablename = overlay["tablename"]
            list_id = "profile-list-%s-%s" % (tablename, overlay["index"])
            layer = {"name": T(overlay["label"]),
                     "id": list_id,
                     "active": True,
                     }
            filter = overlay.get("filter", None)
            marker = overlay.get("marker", None)
            if marker:
                marker = db(mtable.name == marker).select(mtable.image,
                                                          mtable.height,
                                                          mtable.width,
                                                          limitby = (0, 1)
                                                          ).first()
            layer_id = None
            layer_name = overlay.get("layer", None)
            if layer_name:
                row = db(ftable.name == layer_name).select(ftable.layer_id,
                                                           limitby = (0, 1)
                                                           ).first()
                if row:
                    layer_id = row.layer_id
            if layer_id:
                layer["layer_id"] = layer_id
                resource = s3dbresource(tablename)
                filter_url = ""
                first = True
                if context:
                    filters = cserialize_url(resource)
                    for f in filters:
                        sep = "" if first else "&"
                        filter_url = "%s%s%s=%s" % (filter_url, sep, f, filters[f])
                        first = False
                if filter:
                    filters = filter.serialize_url(resource)
                    for f in filters:
                        sep = "" if first else "&"
                        filter_url = "%s%s%s=%s" % (filter_url, sep, f, filters[f])
                        first = False
                if filter_url:
                    layer["filter"] = filter_url
            else:
                layer["tablename"] = tablename
                map_url = overlay.get("map_url", None)
                if not map_url:
                    # Build one
                    c, f = tablename.split("_", 1)
                    map_url = URL(c=c, f=f, extension="geojson")
                    resource = s3dbresource(tablename)
                    first = True
                    if context:
                        filters = cserialize_url(resource)
                        for f in filters:
                            sep = "?" if first else "&"
                            map_url = "%s%s%s=%s" % (map_url, sep, f, filters[f])
                            first = False
                    if filter:
                        filters = filter.serialize_url(resource)
                        for f in filters:
                            sep = "?" if first else "&"
                            map_url = "%s%s%s=%s" % (map_url, sep, f, filters[f])
                            first = False
                layer["url"] = map_url

            if marker:
                layer["marker"] = marker

            fappend(layer)

        # Additional layers, e.g. for primary resource
        profile_layers = s3db.get_config(r.tablename, "profile_layers")
        if profile_layers:
            for layer in profile_layers:
                fappend(layer)

        # Default viewport
        lat = widget_get("lat", None)
        lon = widget_get("lon", None)

        map = current.gis.show_map(height = height,
                                   lat = lat,
                                   lon = lon,
                                   width = width,
                                   bbox = bbox,
                                   collapsed = True,
                                   feature_resources = feature_resources,
                                   )

        # Button to go full-screen
        fullscreen = A(ICON("fullscreen"),
                       _href = URL(c="gis", f="map_viewing_client"),
                       _class = "gis_fullscreen_map-btn",
                       # If we need to support multiple maps on a page
                       #_map = "default",
                       _title = T("View full screen"),
                       )
        s3 = current.response.s3
        if s3.debug:
            script = "/%s/static/scripts/S3/s3.gis.fullscreen.js" % current.request.application
        else:
            script = "/%s/static/scripts/S3/s3.gis.fullscreen.min.js" % current.request.application
        s3.scripts.append(script)

        # Render the widget
        output = DIV(fullscreen,
                     H4(icon,
                        label,
                        _class = "profile-sub-header",
                        ),
                     DIV(map,
                         _class = "card-holder",
                         ),
                     _class = _class,
                     )

        return output

    # -------------------------------------------------------------------------
    def _report(self, r, widget, **attr):
        """
            Generate a Report widget

            Args:
                r: the CRUDRequest instance
                widget: the widget as a tuple: (label, type, icon)
                attr: controller attributes for the request
        """

        widget_get = widget.get

        # Parse context
        context = widget_get("context", None)
        tablename = widget_get("tablename", None)
        resource, context = self._resolve_context(r, tablename, context)

        # Widget filter option
        widget_filter = widget_get("filter", None)
        if widget_filter:
            resource.add_filter(widget_filter)

        # Use the widget-index to create a unique ID
        widget_id = "profile-report-%s-%s" % (tablename, widget["index"])

        # Define the Pivot Table
        report = S3Report()
        report.resource = resource
        ajaxurl = widget_get("ajaxurl", None)
        contents = report.widget(r,
                                 widget_id = widget_id,
                                 ajaxurl = ajaxurl,
                                 **attr)

        # Card holder label and icon
        label = widget_get("label", "")
        if label and isinstance(label, str):
            label = current.T(label)
        icon = widget_get("icon", "")
        if icon:
            icon = ICON(icon)

        _class = self._lookup_class(r, widget)

        # Render the widget
        output = DIV(H4(icon, label,
                        _class = "profile-sub-header",
                        ),
                     DIV(contents,
                         _class = "card-holder",
                         ),
                     _class = _class,
                     )

        return output

    # -------------------------------------------------------------------------
    def _organizer(self, r, widget, **attr):
        """
            Generate an Organizer widget

            Args:
                r: the CRUDRequest instance
                widget: the widget configuration (a dict)
                attr: controller attributes for the request
        """

        from .organizer import S3Organizer, S3OrganizerWidget

        widget_get = widget.get

        # Card holder label and icon
        profile_label = widget_get("label", "")
        if profile_label and isinstance(profile_label, str):
            profile_label = current.T(profile_label)
        icon = widget_get("icon", "")
        if icon:
            icon = ICON(icon)
        _class = self._lookup_class(r, widget)

        # Get base URL
        # - we use an explicit URL here (resource native or component) because
        #   the create-popup requires it anyway, so we can pass the organizer
        #   Ajax lookups through it as well
        # - when accessing the target table as component, remember to also
        #   specify "master" and "component" (see further down)
        base_url = widget_get("url")
        if not base_url:
            return DIV(H4(icon,
                          profile_label,
                          _class = "profile-sub-header",
                          ),
                       DIV(DIV("Error: missing widget URL", _class="error"),
                           _class = "card-holder",
                           ),
                       _class = _class,
                       )

        # Construct Ajax URL from base URL
        parsed = base_url.split("?")
        parsed[0] += "/organize.json"
        ajax_url = "?".join(parsed)

        # Get the target resource (customised+filtered)
        tablename = widget_get("tablename", None)
        resource = current.s3db.resource(tablename)
        r.customise_resource(tablename)

        # Parse the resource organizer config
        config = S3Organizer.parse_config(resource)

        # Generate organizer config for this resource
        table = resource.table
        permitted = current.auth.s3_has_permission

        start = config["start"]
        end = config["end"]

        get_config = resource.get_config
        resource_config = {
            "ajaxURL": ajax_url,
            "useTime": config.get("use_time"),
            "baseURL": base_url,
            "labelCreate": s3_str(get_crud_string(tablename, "label_create")),
            "insertable": get_config("insertable", True) and \
                          permitted("create", table),
            "editable": get_config("editable", True) and \
                        permitted("update", table),
            "startEditable": start.field and start.field.writable,
            "durationEditable": end and end.field and end.field.writable,
            "deletable": get_config("deletable", True) and \
                         permitted("delete", table),
            "start": start.selector if start else None,
            "end": end.selector if end else None,
            }

        # Description Labels
        labels = []
        for rfield in config["description"]:
            label = rfield.label
            if label is not None:
                label = s3_str(label)
            labels.append((rfield.colname, label))
        resource_config["columns"] = labels

        # Colors
        color = config.get("color")
        if color:
            resource_config["color"] = color.colname
            resource_config["colors"] = config.get("colors")

        # Use the widget-index to create a unique ID
        widget_id = "profile-organizer-%s-%s" % (tablename, widget["index"])

        # Generate form key
        formkey = uuid4().hex

        # Determine the formname (see also S3Organizer.formname)
        master = widget_get("master")
        component = widget_get("component")
        if master and component:
            # Override default formname when accessing the target
            # table as a component of another resource:
            # - master: "master_tablename/master_record_id"
            # - component: "component_alias"
            formname = "%s/%s/organizer" % (master, component)
        else:
            # Use default formname
            formname = "%s/organizer" % tablename

        # Store form key in session
        session = current.session
        keyname = "_formkey[%s]" % formname
        session[keyname] = session.get(keyname, [])[-9:] + [formkey]

        # Instantiate Organizer Widget
        organizer = S3OrganizerWidget([resource_config])
        contents = organizer.html(widget_id = widget_id,
                                  formkey = formkey,
                                  )

        # Render the widget
        output = DIV(H4(icon,
                        profile_label,
                        _class = "profile-sub-header",
                        ),
                     DIV(contents,
                         _class = "card-holder profile-organizer",
                         ),
                     _class = _class,
                     )

        return output

    # -------------------------------------------------------------------------
    @staticmethod
    def _lookup_class(r, widget):
        """
            Provide the column-width class for the widgets

            Args:
                r: the CRUDRequest
                widget: the widget config (dict)
        """

        page_cols = current.s3db.get_config(r.tablename, "profile_cols")
        if not page_cols:
            page_cols = 2
        widget_cols = widget.get("colspan", 1)
        span = int(12 / page_cols) * widget_cols

        # Default (=foundation)
        return "profile-widget medium-%s columns" % span

    # -------------------------------------------------------------------------
    @staticmethod
    def _create_popup(r, widget, list_id, resource, context, numrows):
        """
            Render an action link for a create-popup (used in data lists
            and data tables).

            Args:
                r: the CRUDRequest instance
                widget: the widget definition as dict
                list_id: the list ID
                resource: the target resource
                context: the context filter
                numrows: the total number of rows in the list/table
        """

        create = ""

        widget_get = widget.get

        insert = widget_get("insert", True)
        if not insert:
            return create

        table = resource.table
        tablename = resource.tablename

        # Default to primary REST controller for the resource being added
        c, f = tablename.split("_", 1)
        create_controller = widget_get("create_controller")
        if create_controller:
            c = create_controller
        create_function = widget_get("create_function")
        if create_function:
            f = create_function

        permit = current.auth.s3_has_permission
        create_ok = permit("create", table, c=c, f=f)
        if create_ok:
            if not create_controller or not create_function:
                # Assume not component context
                create_ok = permit("update", r.table, record_id=r.id, c=c, f=f)
        if create_ok:
            #if tablename = "org_organisation":
                # @ToDo: Special check for creating resources on Organisation profile

            # URL-serialize the widget filter
            widget_filter = widget_get("filter")
            if widget_filter:
                url_vars = widget_filter.serialize_url(resource)
            else:
                url_vars = Storage()

            # URL-serialize the context filter
            if context:
                filters = context.serialize_url(resource)
                for selector in filters:
                    url_vars[selector] = filters[selector]

            # URL-serialize the widget default
            default = widget_get("default")
            if default:
                k, v = default.split("=", 1)
                url_vars[k] = v

            # URL-serialize the list ID (refresh-target of the popup)
            url_vars.refresh = list_id

            # Indicate that popup comes from profile (and which)
            url_vars.profile = r.tablename

            # Add a var to allow special cutomise rules
            create_var = widget_get("create_var")
            if create_var:
                url_vars[create_var] = 1

            # CRUD string
            label_create = widget_get("label_create", None)
            # Activate if-required
            #if label_create and isinstance(label_create, str):
            if label_create:
                label_create = current.T(label_create)
            else:
                label_create = get_crud_string(tablename, "label_create")

            # Popup URL
            component = widget_get("create_component", None)
            if component:
                args = [r.id, component, "create.popup"]
            else:
                args = widget_get("create_args", ["create.popup"])
            add_url = URL(c=c, f=f, args=args, vars=url_vars)

            if callable(insert):
                # Custom widget
                create = insert(r, list_id, label_create, add_url)

            else:
                # Standard action button
                create = A(label_create,
                           _href = add_url,
                           _class = "action-btn profile-add-btn s3_modal",
                           )

            if widget_get("type") == "datalist":

                # If this is a multiple=False widget and we already
                # have a record, we hide the create-button
                multiple = widget_get("multiple", True)
                if not multiple and hasattr(create, "update"):
                    if numrows:
                        create.update(_style = "display:none")
                    else:
                        create.update(_style = "display:block")
                    # Script to hide/unhide the create-button on Ajax
                    # list updates
                    create_id = create["_id"]
                    if not create_id:
                        create_id = "%s-add-button" % list_id
                        create.update(_id = create_id)
                    script = \
'''$('#%(list_id)s').on('listUpdate',function(){
$('#%(create_id)s').css({display:$(this).datalist('getTotalItems')?'none':'block'})
})''' % {"list_id": list_id,
         "create_id": create_id,
         }
                    current.response.s3.jquery_ready.append(script)

        return create

# END =========================================================================
