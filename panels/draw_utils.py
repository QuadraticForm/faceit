import bpy
import textwrap


def draw_panel_dropdown_expander(layout, data, prop, custom_text):
    if data.get(prop) == 0:
        icon = 'TRIA_RIGHT'
    else:  # data.get(prop) == 1:
        icon = 'TRIA_DOWN'
    # icon = 'TRIA_DOWN' if data.get(prop) else 'TRIA_RIGHT',
    layout.prop(data, str(prop), text=custom_text, icon=icon, icon_only=True, emboss=False
                )


def draw_web_link(layout, link, text_ui='', show_always=False):
    '''Draws a Web @link in the given @layout. Optionally with plain @text_ui'''
    if bpy.context.preferences.addons['faceit'].preferences.web_links or show_always:
        web = layout.operator('faceit.open_web', text=text_ui, icon='QUESTION')
        web.link = link


def draw_text_block(layout, text='', heading='', heading_icon='ERROR') -> None:
    '''wrap a block of text into multiple lines'''
    box = layout.box()
    if heading:
        row = box.row()
        row.label(text=heading, icon=heading_icon)
    for txt_row in textwrap.wrap(text, 55):
        row = box.row()
        row.label(text=txt_row)
