# -*- coding: utf-8 -*-
"""
ngrok 辅助脚本 - 创建外网访问隧道
解决内网无法访问的问题
"""
import os
import sys
import subprocess

def setup_ngrok():
    """安装并启动 ngrok"""
    print("=" * 50)
    print("ngrok 外网隧道助手")
    print("=" * 50)
    
    # 检查是否已安装
    try:
        import pyngrok
        print("✓ pyngrok 已安装")
    except ImportError:
        print("正在安装 pyngrok...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyngrok"], check=True)
        print("✓ 安装完成")
    
    from pyngrok import ngrok
    
    # 启动隧道
    print("\n正在创建隧道...")
    print("(首次使用需要登录 ngrok.com 获取 authtoken)")
    print("")
    
    try:
        # 连接到 5000 端口
        public_url = ngrok.connect(5000, "http")
        
        print("=" * 50)
        print("✓ 隧道创建成功！")
        print("=" * 50)
        print(f"\n外网访问地址:")
        print(f"  {public_url}")
        print(f"\n二维码会自动使用这个地址")
        print(f"\n手机可以直接扫码访问！")
        print("\n" + "=" * 50)
        print("按 Ctrl+C 停止隧道")
        print("=" * 50)
        
        # 更新 .env 文件
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 替换或添加 SERVER_URL
            if 'SERVER_URL=' in content:
                lines = content.split('\n')
                new_lines = []
                for line in lines:
                    if line.startswith('SERVER_URL='):
                        new_lines.append(f'SERVER_URL={public_url}')
                    else:
                        new_lines.append(line)
                content = '\n'.join(new_lines)
            else:
                content += f'\nSERVER_URL={public_url}\n'
            
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"\n✓ 已自动更新 .env 文件")
        
        # 保持运行
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n正在关闭隧道...")
            ngrok.disconnect(public_url)
            print("✓ 已关闭")
            
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        print("\n可能原因:")
        print("1. 需要先注册 ngrok 账号并设置 authtoken")
        print("2. 访问 https://ngrok.com 注册")
        print("3. 运行: ngrok authtoken YOUR_TOKEN")
        
        # 尝试安装 ngrok 命令行工具
        try:
            from pyngrok import ngrok
            print("\n尝试安装 ngrok...")
            ngrok.install_ngrok()
            print("✓ 安装完成，请重新运行此脚本")
        except Exception as e2:
            print(f"✗ 安装失败: {e2}")

if __name__ == '__main__':
    setup_ngrok()
