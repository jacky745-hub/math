"""全系統唯一的 SQLAlchemy 實例。

所有模組都必須 `from src.extensions import db`，不可再自行建立 SQLAlchemy()，
並且只在 create_app() 內呼叫一次 db.init_app(app)。
這是避免「The current Flask app is not registered with this 'SQLAlchemy' instance」的關鍵。
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
