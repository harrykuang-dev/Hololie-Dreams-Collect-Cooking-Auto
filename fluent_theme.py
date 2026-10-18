"""Cooking's native ttk visual theme. Raster tiles are created once per DPI."""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageFont, ImageTk

BG, SURFACE, TEXT, MUTED = '#F5F5F5', '#FFFFFF', '#242424', '#616161'
ACCENT, HOVER, PRESSED, ACTION_TEXT = '#F15B60', '#E9545A', '#E24D54', '#211010'
BORDER, CARD_BORDER = '#D1D1D1', '#E5E5E5'


class FluentTheme:
    def __init__(self, root, scale):
        self.root, self.scale, self.images = root, scale, []
        self.style = s = ttk.Style(root)
        s.theme_use('clam')
        s.configure('.', font=('Segoe UI', 10), background=BG, foreground=TEXT)
        s.configure('TFrame', background=BG)
        s.configure('Surface.TFrame', background=SURFACE)
        s.configure('TLabel', background=SURFACE, foreground=TEXT)
        s.configure('Title.TLabel', background=BG, font=('Segoe UI', 18, 'bold'))
        s.configure('Muted.TLabel', foreground=MUTED)
        s.configure('Card.TLabel', background=SURFACE)
        s.configure('CardMuted.TLabel', background=SURFACE, foreground=MUTED)
        s.configure('Intro.TLabel', background=BG, foreground=MUTED)
        s.configure('Count.TLabel', font=('Segoe UI', 20, 'bold'))
        self.surface('Card', SURFACE, CARD_BORDER, 8, BG)
        self.surface('Field', SURFACE, BORDER, 4, SURFACE)
        self.surface('FocusField', SURFACE, ACCENT, 4, SURFACE)
        self.surface('DisabledField', '#F0F0F0', CARD_BORDER, 4, SURFACE)
        self.button('Primary', ACCENT, HOVER, PRESSED, ACTION_TEXT)
        self.button('Secondary', SURFACE, '#F5F5F5', '#EBEBEB', TEXT, BORDER)
        self.button('Subtle', BG, '#EBEBEB', '#E0E0E0', MUTED)
        self.button('Info', SURFACE, '#FCEBEC', '#F8DCDD', MUTED)
        self.button('PageInfo', BG, '#FCEBEC', '#F8DCDD', MUTED)
        s.configure('Info.TButton', padding=0)
        s.configure('PageInfo.TButton', padding=0)
        def help_icon(draw, size, unit):
            w,h=size
            draw.ellipse((unit,unit,w-unit,h-unit),outline=MUTED,width=max(1,round(unit)))
            font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',round(h*.72))
            draw.text((w*.5,h*.49),'?',font=font,fill=MUTED,anchor='mm')
        self.help_icon=self.photo((16,16),help_icon)
        s.configure('Subtle.TButton', padding=(self.px(8), self.px(4)))
        self.operation_icons = {kind: self.symbol(kind, ACTION_TEXT) for kind in ('play', 'pause')}
        self.stop_icon = self.symbol('stop', TEXT)
        self.disabled_play_icon = self.symbol('play', '#A0A0A0')
        self.disabled_stop_icon = self.symbol('stop', '#A0A0A0')
        self.checkboxes()
        self.radios()
        self.fields()
        s.configure('Page.TCheckbutton', background=BG)
        s.map('Page.TCheckbutton', background=[('active',BG)])
        s.configure('Vertical.TScrollbar', background='#D6D6D6', troughcolor=SURFACE,
                    borderwidth=0, arrowsize=0, width=self.px(6))
        s.map('Vertical.TScrollbar', background=[('pressed','#999999'),('active','#ADADAD')])
        s.layout('Vertical.TScrollbar',[('Vertical.Scrollbar.trough',{'sticky':'ns','children':[
            ('Vertical.Scrollbar.thumb',{'expand':True,'sticky':'nswe'})]})])

    def px(self, value):
        return max(1, round(value * self.scale))

    def photo(self, logical_size, paint):
        size = tuple(self.px(x) for x in logical_size)
        image = Image.new('RGBA', tuple(x * 4 for x in size))
        paint(ImageDraw.Draw(image), image.size, self.scale * 4)
        photo = ImageTk.PhotoImage(image.resize(size, Image.Resampling.LANCZOS), master=self.root)
        self.images.append(photo)
        return photo

    def tile(self, fill, border, radius, background):
        def paint(draw, size, unit):
            draw.rectangle((0, 0, *size), fill=background)
            draw.rounded_rectangle((unit / 2, unit / 2, size[0] - unit / 2, size[1] - unit / 2),
                                   radius=radius * unit, fill=fill, outline=border,
                                   width=max(1, round(unit)))
        return self.photo((320, 64), paint)

    def surface(self, name, fill, border, radius, background):
        s = self.style
        s.element_create(name + '.surface', 'image', self.tile(fill, border, radius, background),
                         border=self.px(radius + 2), width=self.px(radius*2+5), height=self.px(radius*2+5), sticky='nswe')
        s.layout(name + '.TFrame', [(name + '.surface', {'sticky': 'nswe'})])
        s.configure(name + '.TFrame', background=fill)

    def button(self, name, fill, hover, pressed, foreground, border=None):
        s = self.style
        backdrop = SURFACE if name == 'Info' else BG
        normal = self.tile(fill, border or fill, 6, backdrop)
        hot = self.tile(hover, border or hover, 6, backdrop)
        down = self.tile(pressed, border or pressed, 6, backdrop)
        disabled = self.tile('#F0F0F0', CARD_BORDER, 6, backdrop)
        focus = self.tile(fill, '#A9343B' if name == 'Primary' else ACCENT, 6, backdrop)
        s.element_create(name + '.button', 'image', normal, ('disabled', disabled),
                         ('pressed', down), ('active', hot), ('focus', focus),
                         border=self.px(6), width=self.px(17), height=self.px(17), sticky='nswe')
        s.layout(name + '.TButton', [(name + '.button', {'sticky': 'nswe', 'children': [
            ('Button.padding', {'sticky': 'nswe', 'children': [('Button.label', {'sticky': 'nswe'})]})]})])
        s.configure(name + '.TButton', foreground=foreground, background=backdrop,
                    lightcolor=backdrop,darkcolor=backdrop,bordercolor=backdrop,relief='flat',
                    font=('Segoe UI', 10), padding=(self.px(10), self.px(5)), borderwidth=0)
        s.map(name + '.TButton', foreground=[('disabled', '#929292')],
              background=[('disabled',backdrop),('pressed',backdrop),('active',backdrop)],
              lightcolor=[('disabled',backdrop),('pressed',backdrop),('active',backdrop)],
              darkcolor=[('disabled',backdrop),('pressed',backdrop),('active',backdrop)])

    def symbol(self, kind, color):
        def paint(draw, size, unit):
            w, h = size
            if kind == 'play': draw.polygon([(w*.25, h*.15), (w*.8, h*.5), (w*.25, h*.85)], fill=color)
            elif kind == 'pause':
                for x in (.24, .58): draw.rectangle((w*x, h*.2, w*(x+.18), h*.8), fill=color)
            else: draw.rounded_rectangle((w*.2, h*.2, w*.8, h*.8), radius=unit, fill=color)
        return self.photo((16, 16), paint)

    def checkboxes(self):
        def box(selected=False, disabled=False):
            def paint(draw, size, unit):
                w,h=size
                fill='#E5E5E5' if disabled else ACCENT if selected else SURFACE
                outline=CARD_BORDER if disabled else ACCENT if selected else BORDER
                draw.rounded_rectangle((unit,unit,w-unit,h-unit),radius=3*unit,
                                       fill=fill,outline=outline,width=max(1,round(unit)))
                if selected:draw.line([(w*.25,h*.5),(w*.43,h*.68),(w*.76,h*.32)],
                                      fill='#A0A0A0' if disabled else ACTION_TEXT,width=max(1,round(unit*1.5)))
            return self.photo((18, 18), paint)
        s = self.style
        s.element_create('Cooking.check', 'image', box(), ('disabled', 'selected', box(True, True)),
                         ('disabled', box(False, True)), ('selected', box(True)),sticky='')
        s.layout('TCheckbutton', [('Checkbutton.padding', {'sticky': 'nswe', 'children': [
            ('Cooking.check', {'side': 'left','sticky':''}), ('Checkbutton.focus', {'side': 'left', 'sticky': 'nswe',
             'children': [('Checkbutton.label', {'sticky': 'nswe'})]})]})])
        s.configure('TCheckbutton', background=BG, padding=0,
                    indicatormargin=(0, 0, self.px(6), 0))
        s.map('TCheckbutton', background=[('active', BG)], foreground=[('disabled', '#A0A0A0')])

    def radios(self):
        def indicator(selected=False, disabled=False):
            def paint(draw,size,unit):
                w=h=size[1]
                color='#BDBDBD' if disabled else ACCENT if selected else '#8A8A8A'
                draw.ellipse((unit,unit,w-unit,h-unit),fill=SURFACE,outline=color,
                             width=max(1,round(unit*(2 if selected else 1))))
                if selected:draw.ellipse((w*.32,h*.32,w*.68,h*.68),fill=color)
            return self.photo((24,18),paint)
        s=self.style
        s.element_create('Cooking.radio','image',indicator(),
                         ('disabled','selected',indicator(True,True)),
                         ('disabled',indicator(False,True)),('selected',indicator(True)),sticky='')
        s.layout('TRadiobutton',[('Radiobutton.padding',{'sticky':'nswe','children':[
            ('Cooking.radio',{'side':'left'}),
            ('Radiobutton.focus',{'side':'left','sticky':'nswe','children':[
                ('Radiobutton.label',{'sticky':'nswe'})]})]})])
        s.configure('TRadiobutton',background=SURFACE,padding=(0,self.px(4)),
                    indicatormargin=(0,0,self.px(6),0))
        s.map('TRadiobutton',foreground=[('disabled','#A0A0A0')],background=[('active',SURFACE)])

    def fields(self):
        s = self.style
        normal = self.tile(SURFACE, BORDER, 4, SURFACE)
        focus = self.tile(SURFACE, ACCENT, 4, SURFACE)
        disabled = self.tile('#F0F0F0', CARD_BORDER, 4, SURFACE)
        # Match High & Low's framed native entry: five logical pixels plus
        # the native entry's one physical pixel of text inset on each side.
        inset_y=self.px(5)+1
        s.element_create('Cooking.field','image',normal,('disabled',disabled),('focus',focus),
                         border=(self.px(6),inset_y,self.px(6),inset_y),
                         width=self.px(13),height=inset_y*2+1,sticky='nswe')
        s.layout('TEntry', [('Cooking.field', {'sticky': 'nswe', 'children': [
            ('Entry.padding', {'sticky': 'nswe', 'children': [('Entry.textarea', {'sticky': 'nswe'})]})]})])
        s.configure('TEntry', padding=(self.px(8), 0), borderwidth=0,
                    fieldbackground=SURFACE, foreground=TEXT, insertcolor=TEXT)
        s.map('TEntry', fieldbackground=[('readonly', SURFACE), ('disabled', '#F0F0F0')],
              foreground=[('disabled', '#929292')], selectbackground=[('!disabled', ACCENT)],
              selectforeground=[('!disabled', ACTION_TEXT)])
        def arrow(draw, size, unit):
            w, h = size
            draw.line([(w*.3,h*.4),(w*.5,h*.6),(w*.7,h*.4)], fill=MUTED, width=max(1,round(unit)))
        s.element_create('Series.arrow', 'image', self.photo((28,14),arrow), sticky='')
        s.layout('TCombobox', [('Cooking.field', {'sticky': 'nswe', 'children': [
            ('Series.arrow', {'side': 'right', 'sticky': 'ns'}),
            ('Combobox.padding', {'sticky': 'nswe', 'children': [('Combobox.textarea', {'sticky': 'nswe'})]})]})])
        s.configure('TCombobox', padding=(self.px(8), 0), fieldbackground=SURFACE,
                    borderwidth=0, arrowsize=self.px(13))
        s.map('TCombobox', fieldbackground=[('readonly', SURFACE)],
              selectbackground=[('readonly', SURFACE)], selectforeground=[('readonly', TEXT)])
