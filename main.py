from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.animation import Animation
from kivy.utils import get_color_from_hex

from PIL import Image, ImageOps
from pathlib import Path
import threading
import io
import os

# ---- 中文字体：优先用打包字体（不依赖设备 ROM），系统字体兜底 ----
_BUNDLED_FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'DroidSansFallbackFull.ttf')
_CJK_FALLBACKS = [
    _BUNDLED_FONT,
    '/system/fonts/DroidSansFallback.ttf',
    '/system/fonts/NotoSansCJKsc-Regular.otf',
]
for _f in _CJK_FALLBACKS:
    if os.path.exists(_f):
        try:
            LabelBase.register(name='Roboto', fn_regular=_f)
            break
        except Exception:
            continue

try:
    from plyer import filechooser
    HAS_PLYER = True
except Exception:
    HAS_PLYER = False

OUTPUT_DESC = '下载文件夹 (Download)'


def request_storage_permission():
    """Android 6-9 (API 24-28) 需要运行时请求写权限；API 29+ 走 MediaStore 不需要。"""
    if not _is_android():
        return
    if _sdk_int() >= 29:
        return
    try:
        from plyer import permissions
        permissions.request_permissions(['android.permission.WRITE_EXTERNAL_STORAGE'])
    except Exception:
        pass


def get_output_dir():
    return OUTPUT_DESC


def _is_android():
    try:
        import jnius
        return True
    except Exception:
        return False


def _sdk_int():
    try:
        from jnius import autoclass
        Build = autoclass('android.os.Build$VERSION')
        return int(Build.SDK_INT)
    except Exception:
        return 0


def save_to_downloads(filename, mime, data):
    """写入公共下载目录，返回文件名。"""
    if _is_android():
        if _sdk_int() >= 29:
            _save_mediastore(filename, mime, data)
        else:
            _save_legacy(filename, data)
        return filename
    out = Path.home() / 'Desktop'
    out.mkdir(parents=True, exist_ok=True)
    (out / filename).write_bytes(data)
    return str(out / filename)


def _save_mediastore(filename, mime, data):
    from jnius import autoclass
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    MediaStore = autoclass('android.provider.MediaStore')
    ContentValues = autoclass('android.content.ContentValues')
    activity = PythonActivity.mActivity
    resolver = activity.getContentResolver()
    values = ContentValues()
    values.put(MediaStore.Downloads.DISPLAY_NAME, filename)
    values.put(MediaStore.Downloads.MIME_TYPE, mime)
    uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
    if uri is None:
        raise IOError('无法创建下载文件（存储空间可能已满）')
    out = resolver.openOutputStream(uri)
    if out is None:
        raise IOError('无法写入下载文件夹')
    try:
        out.write(data)
    finally:
        out.close()


def _save_legacy(filename, data):
    d = '/storage/emulated/0/Download'
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, filename)
    with open(path, 'wb') as f:
        f.write(data)
    return path


class ConverterApp(App):
    def build(self):
        Window.clearcolor = (0.12, 0.12, 0.14, 1)
        self.selected_files = []
        self._busy = False
        request_storage_permission()

        root = BoxLayout(orientation='vertical', padding=12, spacing=10)

        self.title = Label(
            text='[b]万能格式转换器[/b]',
            markup=True, font_size='22sp', size_hint_y=None, height='48dp'
        )
        root.add_widget(self.title)

        self.status = Label(
            text='请选择文件', font_size='15sp',
            color=(0.8, 0.8, 0.8, 1), size_hint_y=None, height='36dp'
        )
        root.add_widget(self.status)

        file_btn_row = BoxLayout(size_hint_y=None, height='52dp', spacing=8)
        pick_btn = Button(text='选择文件/图片', font_size='15sp',
                          background_color=(0.15, 0.45, 0.95, 1))
        pick_btn.bind(on_release=self.pick_files)
        pick_btn.bind(on_press=self._press_anim, on_release=self._release_anim)
        file_btn_row.add_widget(pick_btn)
        clear_btn = Button(text='清空', font_size='15sp',
                           background_color=(0.4, 0.4, 0.42, 1))
        clear_btn.bind(on_release=self.clear_files)
        clear_btn.bind(on_press=self._press_anim, on_release=self._release_anim)
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
            values=['图片 → PDF', '图片 → PNG', '图片 → JPG'],
            font_size='14sp', size_hint_x=1.4
        )
        opt_row.add_widget(self.conv_type)
        root.add_widget(opt_row)

        self.convert_btn = Button(
            text='开始转换', font_size='17sp', size_hint_y=None, height='56dp',
            background_color=(0.1, 0.75, 0.4, 1)
        )
        self.convert_btn.bind(on_release=self.do_convert)
        self.convert_btn.bind(on_press=self._press_anim, on_release=self._release_anim)
        root.add_widget(self.convert_btn)

        self.out_dir_label = Label(
            text=f'输出到: {get_output_dir()}', font_size='11sp',
            color=(0.6, 0.6, 0.65, 1), size_hint_y=None, height='24dp'
        )
        root.add_widget(self.out_dir_label)

        self._intro_animation(root)
        return root

    def _intro_animation(self, root):
        """开场动画：标题下落+淡入，控件依次浮现。"""
        for i, child in enumerate(root.children):
            child.opacity = 0
            child.y -= 30 * (i + 1)
            anim = Animation(opacity=1, y=child.y + 30 * (i + 1),
                             duration=0.35, t='out_quad')
            anim.start(child)

    def _press_anim(self, btn):
        Animation.cancel_all(btn, 'scale', 'opacity')
        anim = Animation(scale=0.94, opacity=0.85, duration=0.06, t='out_quad')
        anim.start(btn)

    def _release_anim(self, btn):
        Animation.cancel_all(btn, 'scale', 'opacity')
        anim = Animation(scale=1.0, opacity=1.0, duration=0.12, t='out_back')
        anim.start(btn)

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
        if self._busy:
            return
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
        if self._busy:
            return
        if not self.selected_files:
            self.show_popup('提示', '请先选择文件')
            return
        self._busy = True
        self.convert_btn.disabled = True
        conv = self.conv_type.text
        self.status.text = '转换中...'
        self._start_loading()
        t = threading.Thread(target=self._convert_worker, args=(conv,), daemon=True)
        t.start()

    def _start_loading(self):
        """转换按钮转圈动画。"""
        anim = Animation(rotation=360, duration=0.6) + Animation(rotation=0, duration=0)
        anim.repeat = True
        anim.start(self.convert_btn)

    def _stop_loading(self):
        Animation.cancel_all(self.convert_btn, 'rotation')
        self.convert_btn.rotation = 0

    def _convert_worker(self, conv):
        try:
            results = self._run_conversion(conv)
            Clock.schedule_once(lambda dt: self._on_done(results))
        except Exception as e:
            print(f'[FileConverter] 转换失败: {e}', flush=True)
            Clock.schedule_once(lambda dt: self._on_error())

    def _load_image(self, path):
        """打开图片并应用 EXIF 拍摄方向。"""
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)
        return img

    def _run_conversion(self, conv):
        results = []

        if conv == '图片 → PDF':
            images = []
            try:
                for f in self.selected_files:
                    img = self._load_image(f)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    images.append(img)
                buf = io.BytesIO()
                if len(images) == 1:
                    name = Path(self.selected_files[0]).stem + '.pdf'
                    images[0].save(buf, 'PDF', resolution=100.0)
                else:
                    name = '合并图片.pdf'
                    images[0].save(buf, 'PDF', save_all=True,
                                   append_images=images[1:], resolution=100.0)
                results.append(save_to_downloads(name, 'application/pdf', buf.getvalue()))
            finally:
                for img in images:
                    img.close()

        elif conv in ('图片 → PNG', '图片 → JPG'):
            fmt = 'PNG' if conv.endswith('PNG') else 'JPEG'
            ext = 'png' if fmt == 'PNG' else 'jpg'
            mime = 'image/png' if fmt == 'PNG' else 'image/jpeg'
            for f in self.selected_files:
                img = None
                try:
                    img = self._load_image(f)
                    name = Path(f).stem + '.' + ext
                    buf = io.BytesIO()
                    img.save(buf, fmt)
                    results.append(save_to_downloads(name, mime, buf.getvalue()))
                finally:
                    if img is not None:
                        img.close()

        return results

    def _on_done(self, results):
        self._busy = False
        self.convert_btn.disabled = False
        self._stop_loading()
        self.status.text = f'完成! 生成 {len(results)} 个文件'
        self.status.color = (0.1, 0.9, 0.4, 1)
        anim = (Animation(color=(1, 1, 1, 1), duration=0.3) +
                Animation(color=(0.1, 0.9, 0.4, 1), duration=0.3)) * 3
        anim.start(self.status)
        detail = '\n'.join(Path(p).name for p in results[:10])
        if len(results) > 10:
            detail += f'\n... 共 {len(results)} 个'
        self.show_popup('转换完成', f'已保存到下载文件夹:\n\n{detail}')

    def _on_error(self):
        self._busy = False
        self.convert_btn.disabled = False
        self._stop_loading()
        self.status.text = '转换失败'
        self.status.color = (1, 0.3, 0.3, 1)
        anim = Animation(color=(1, 1, 1, 1), duration=0.4, t='out_bounce')
        anim.start(self.status)
        self.show_popup('错误', '转换失败，请检查所选文件是否为有效的图片文件')

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
