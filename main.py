from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.window import Window

from PIL import Image
from pathlib import Path
import threading

try:
    from plyer import storagepath
    from plyer import filechooser
    HAS_PLYER = True
except Exception:
    HAS_PLYER = False

OUTPUT_DIR = None


def get_output_dir():
    global OUTPUT_DIR
    if OUTPUT_DIR:
        return OUTPUT_DIR
    if HAS_PLYER:
        try:
            OUTPUT_DIR = storagepath.downloads_dir()
            return OUTPUT_DIR
        except Exception:
            pass
    OUTPUT_DIR = str(Path.home())
    return OUTPUT_DIR


class ConverterApp(App):
    def build(self):
        Window.clearcolor = (0.12, 0.12, 0.14, 1)
        self.selected_files = []

        root = BoxLayout(orientation='vertical', padding=12, spacing=10)

        root.add_widget(Label(
            text='[b]万能格式转换器[/b]',
            markup=True, font_size='22sp', size_hint_y=None, height='48dp'
        ))

        self.status = Label(
            text='请选择文件', font_size='15sp',
            color=(0.8, 0.8, 0.8, 1), size_hint_y=None, height='36dp'
        )
        root.add_widget(self.status)

        file_btn_row = BoxLayout(size_hint_y=None, height='52dp', spacing=8)
        pick_btn = Button(text='选择文件/图片', font_size='15sp',
                          background_color=(0.15, 0.45, 0.95, 1))
        pick_btn.bind(on_release=self.pick_files)
        file_btn_row.add_widget(pick_btn)
        clear_btn = Button(text='清空', font_size='15sp',
                           background_color=(0.4, 0.4, 0.42, 1))
        clear_btn.bind(on_release=self.clear_files)
        file_btn_row.add_widget(clear_btn)
        root.add_widget(file_btn_row)

        self.file_list = Label(
            text='', font_size='13sp', halign='left', valign='top',
            color=(0.9, 0.9, 0.9, 1), size_hint_y=None
        )
        self.file_list.bind(texture_size=self.file_list.setter('size'))
        sv = ScrollView(size_hint=(1, 0.45))
        sv.add_widget(self.file_list)
        root.add_widget(sv)

        opt_row = BoxLayout(size_hint_y=None, height='52dp', spacing=8)
        opt_row.add_widget(Label(text='转换类型', font_size='14sp'))
        self.conv_type = Spinner(
            text='图片 → PDF',
            values=['图片 → PDF', '图片 → PNG', '图片 → JPG', 'PDF → 图片'],
            font_size='14sp', size_hint_x=1.4
        )
        opt_row.add_widget(self.conv_type)
        root.add_widget(opt_row)

        convert_btn = Button(
            text='开始转换', font_size='17sp', size_hint_y=None, height='56dp',
            background_color=(0.1, 0.75, 0.4, 1)
        )
        convert_btn.bind(on_release=self.do_convert)
        root.add_widget(convert_btn)

        self.out_dir_label = Label(
            text=f'输出目录: {get_output_dir()}', font_size='11sp',
            color=(0.6, 0.6, 0.65, 1), size_hint_y=None, height='24dp'
        )
        root.add_widget(self.out_dir_label)

        return root

    def pick_files(self, instance):
        if HAS_PLYER:
            try:
                filechooser.open_file(on_selection=self.on_files_selected, multiple=True)
                return
            except Exception:
                pass
        self.show_popup('提示', '当前环境不支持文件选择器')

    def on_files_selected(self, selection):
        if not selection:
            return
        self.selected_files = list(selection)
        self.refresh_list()

    def clear_files(self, instance):
        self.selected_files = []
        self.refresh_list()

    def refresh_list(self):
        if not self.selected_files:
            self.file_list.text = ''
            self.status.text = '请选择文件'
            return
        lines = []
        for f in self.selected_files:
            name = Path(f).name
            lines.append(f'• {name}')
        self.file_list.text = '\n'.join(lines)
        self.status.text = f'已选 {len(self.selected_files)} 个文件'

    def do_convert(self, instance):
        if not self.selected_files:
            self.show_popup('提示', '请先选择文件')
            return
        conv = self.conv_type.text
        self.status.text = '转换中...'
        t = threading.Thread(target=self._convert_worker, args=(conv,), daemon=True)
        t.start()

    def _convert_worker(self, conv):
        try:
            results = self._run_conversion(conv)
            Clock.schedule_once(lambda dt: self._on_done(results))
        except Exception as e:
            Clock.schedule_once(lambda dt, err=str(e): self._on_error(err))

    def _run_conversion(self, conv):
        out_dir = Path(get_output_dir())
        out_dir.mkdir(parents=True, exist_ok=True)
        results = []

        if conv == '图片 → PDF':
            images = []
            for f in self.selected_files:
                img = Image.open(f)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                images.append(img)
            if len(images) == 1:
                name = Path(self.selected_files[0]).stem + '.pdf'
                images[0].save(out_dir / name, 'PDF', resolution=100.0)
            else:
                name = '合并图片.pdf'
                images[0].save(out_dir / name, 'PDF', save_all=True,
                               append_images=images[1:], resolution=100.0)
            results.append(str(out_dir / name))

        elif conv in ('图片 → PNG', '图片 → JPG'):
            fmt = 'PNG' if conv.endswith('PNG') else 'JPEG'
            ext = 'png' if fmt == 'PNG' else 'jpg'
            for f in self.selected_files:
                img = Image.open(f)
                name = Path(f).stem + '.' + ext
                img.save(out_dir / name, fmt)
                results.append(str(out_dir / name))

        elif conv == 'PDF → 图片':
            import fitz
            for f in self.selected_files:
                doc = fitz.open(f)
                for i in range(doc.page_count):
                    pix = doc[i].get_pixmap(dpi=150)
                    name = f'{Path(f).stem}_p{i + 1}.jpg'
                    pix.save(str(out_dir / name))
                    results.append(str(out_dir / name))
                doc.close()

        return results

    def _on_done(self, results):
        self.status.text = f'完成! 生成 {len(results)} 个文件'
        detail = '\n'.join(Path(p).name for p in results[:10])
        if len(results) > 10:
            detail += f'\n... 共 {len(results)} 个'
        self.show_popup('转换完成', f'输出到:\n{get_output_dir()}\n\n{detail}')

    def _on_error(self, err):
        self.status.text = '转换失败'
        self.show_popup('错误', str(err))

    def show_popup(self, title, content):
        box = BoxLayout(orientation='vertical', padding=12, spacing=8)
        lbl = Label(text=content, halign='left', valign='top')
        lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        box.add_widget(lbl)
        btn = Button(text='确定', size_hint_y=None, height='44dp',
                     background_color=(0.15, 0.45, 0.95, 1))
        popup = Popup(title=title, content=box, size_hint=(0.85, 0.5))
        btn.bind(on_release=popup.dismiss)
        box.add_widget(btn)
        popup.open()


if __name__ == '__main__':
    ConverterApp().run()
