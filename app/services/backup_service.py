import os
import io
import json
import threading
import time
from datetime import datetime
from flask import current_app
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from app.modules.system.models import SystemSetting
from app.services.google_service import GoogleIntegrationService
from app import create_app

class BackupService:
    @staticmethod
    def backup_instance_to_drive():
        print("--- 執行 instance/ 資料夾備份任務 ---")
        app = create_app()
        with app.app_context():
            drive, _ = GoogleIntegrationService.get_services(app)
            if not drive:
                print("備份失敗：未找到有效的 Google Drive 憑證。")
                return
                
            backup_files_json = SystemSetting.get('instance_backup_files')
            backup_files = json.loads(backup_files_json) if backup_files_json else []
            if not backup_files: return
                
            folder_name = SystemSetting.get('drive_folder_name', 'Cashier_System_Reports')
            response = drive.files().list(
                q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive', fields='files(id)'
            ).execute()
            
            if response.get('files'):
                folder_id = response['files'][0]['id']
            else:
                folder = drive.files().create(body={'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}, fields='id').execute()
                folder_id = folder.get('id')
                
            for filename in backup_files:
                filepath = os.path.join(current_app.instance_path, filename)
                if not os.path.exists(filepath): continue
                    
                try:
                    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                    backup_filename = f"{os.path.splitext(filename)[0]}_{timestamp}{os.path.splitext(filename)[1]}"
                    media = MediaIoBaseUpload(io.FileIO(filepath, 'rb'), mimetype='application/octet-stream')
                    drive.files().create(body={'name': backup_filename, 'parents': [folder_id]}, media_body=media, fields='id').execute()
                    print(f"成功備份 '{filename}' 至 Google Drive。")
                except Exception as e:
                    print(f"備份 '{filename}' 時發生錯誤：{e}")

class BackupScheduler(threading.Thread):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.running = True

    def run(self):
        with self.app.app_context():
            while self.running:
                frequency = SystemSetting.get('instance_backup_frequency')
                if frequency == 'interval':
                    interval = int(SystemSetting.get('instance_backup_interval_minutes', '1440') or 1440)
                    print(f"下一次備份將在 {interval} 分鐘後執行...")
                    time.sleep(interval * 60)
                    if SystemSetting.get('instance_backup_frequency') == 'interval':
                        BackupService.backup_instance_to_drive()
                else:
                    time.sleep(60 * 5)
                    
    def stop(self):
        self.running = False
        print("備份排程器已停止。")