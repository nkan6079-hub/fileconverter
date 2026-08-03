# 万能格式转换器 (Android)

手机版文件格式转换工具。

## 功能
- 图片 → PDF（多图可合并为一个PDF）
- 图片 → PNG / JPG
- PDF → 图片（每页转一张JPG）

## 打包方式（云端 CI）
1. 把本目录推送到 GitHub 仓库
2. 打开仓库 Actions 页面，运行 "Build Android APK"
3. 构建完成后下载 artifact（APK 文件）
4. 手机安装 APK 即可使用

## 本地开发
```bash
pip install kivy pillow plyer pymupdf
python main.py
```
