import os
import io

try:
    from PIL import Image
    import pillow_heif
except ImportError:
    print("[-] 错误：缺少处理 HEIC 图片的必要运行库。")
    print("[-] 请打开命令提示符(cmd)并运行以下命令：")
    print("    pip install Pillow pillow-heif")
    exit()

def create_android_live_photo(image_bytes, video_path, output_path):
    """
    将 JPG 字节流和视频合并为安卓支持的内嵌式实况照片
    """
    # 1. 读取视频并获取其字节长度
    with open(video_path, 'rb') as vf:
        video_bytes = vf.read()
    
    video_size = len(video_bytes)
    
    # 2. 构造安卓/Google 相册识别的 XMP 元数据
    xmp_xml = f"""<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 5.1.2">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
        xmlns:GCamera="http://ns.google.com/photos/1.0/camera/">
        <GCamera:MicroVideo>1</GCamera:MicroVideo>
        <GCamera:MicroVideoVersion>1</GCamera:MicroVideoVersion>
        <GCamera:MicroVideoOffset>{video_size}</GCamera:MicroVideoOffset>
        <GCamera:MicroVideoPresentationTimestampUs>0</GCamera:MicroVideoPresentationTimestampUs>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>""".encode('utf-8')
    
    # 3. 将 XMP 打包为 JPG 的 APP1 数据段标准格式
    xmp_header = b'http://ns.adobe.com/xap/1.0/\x00'
    app1_payload = xmp_header + xmp_xml
    app1_size = len(app1_payload) + 2
    app1_marker = b'\xff\xe1' + app1_size.to_bytes(2, 'big')
    app1_segment = app1_marker + app1_payload

    # 4. 验证并拼接
    if not image_bytes.startswith(b'\xff\xd8'):
        raise ValueError("传入的图片数据不是有效的 JPG 格式")

    # 在 JPG 的文件头 (FF D8) 之后，立即插入我们的 APP1(XMP) 数据段
    final_image_bytes = image_bytes[:2] + app1_segment + image_bytes[2:]

    # 5. 生成最终文件：写入带标签的图片数据，接着无缝写入视频数据
    with open(output_path, 'wb') as outf:
        outf.write(final_image_bytes)
        outf.write(video_bytes)

def main():
    print("=== 实况照片合并工具 ===")
    folder = input("请输入包含分离实况照片的文件夹路径: ").strip().replace('"', '').replace("'", "")
    
    if not os.path.isdir(folder):
        print("错误：找不到该文件夹！")
        return
        
    output_folder = os.path.join(folder, "Live Photo")
    os.makedirs(output_folder, exist_ok=True)
    
    # 提取所有不带后缀的文件名
    files = os.listdir(folder)
    base_names = set()
    for f in files:
        if os.path.isfile(os.path.join(folder, f)):
            name, _ = os.path.splitext(f)
            base_names.add(name)
            
    success_count = 0
    print(f"[*] 正在扫描文件夹...\n")
    
    for base in base_names:
        img_path = None
        vid_path = None
        img_ext_used = ""
        
        # 匹配图片
        for ext in ['.jpg', '.jpeg', '.heic', '.JPG', '.JPEG', '.HEIC']:
            p = os.path.join(folder, base + ext)
            if os.path.exists(p):
                img_path = p
                img_ext_used = ext.lower()
                break
                
        # 匹配视频
        for ext in ['.mov', '.mp4', '.MOV', '.MP4']:
            p = os.path.join(folder, base + ext)
            if os.path.exists(p):
                vid_path = p
                break
                
        # 找到一对
        if img_path and vid_path:
            output_file = os.path.join(output_folder, base + ".jpg") # 最终一律输出为 .jpg
            
            print(f"[*] 正在处理: {base} ...", end=" ", flush=True)
            try:
                # 步骤 A：获取 JPG 的二进制数据
                if img_ext_used == '.heic':
                    # 读取 HEIC 并在内存中无损转换为 JPG (保留 EXIF 数据)
                    heif_file = pillow_heif.read_heif(img_path)
                    image = Image.frombytes(
                        heif_file.mode, 
                        heif_file.size, 
                        heif_file.data, 
                        "raw"
                    )
                    
                    img_buffer = io.BytesIO()
                    exif_data = heif_file.info.get("exif")
                    
                    if exif_data:
                        image.save(img_buffer, format="JPEG", exif=exif_data, quality=100)
                    else:
                        image.save(img_buffer, format="JPEG", quality=100)
                        
                    image_bytes = img_buffer.getvalue()
                else:
                    # 如果本来就是 JPG，直接读取
                    with open(img_path, 'rb') as f:
                        image_bytes = f.read()

                # 步骤 B：合并
                create_android_live_photo(image_bytes, vid_path, output_file)
                print("成功！")
                success_count += 1
                
            except Exception as e:
                print(f"失败！错误信息: {e}")
                
    print(f"\n[+] 处理完成！共成功合成 {success_count} 张实况照片。")
    print(f"[+] 文件已保存在: {output_folder}")

if __name__ == "__main__":
    main()
    input("\n按回车键退出...")