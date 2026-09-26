# EBS R12 Explorer — Django Edition

Oracle EBS R12 Schema & Dataset Management Platform.

## 🚀 Quick Start

**Windows:** `run.bat`
**Mac/Linux:** `chmod +x run.sh && ./run.sh`

Then open: **http://localhost:8000**

## 🔐 Default Accounts

| Username | Password | Role |
|----------|----------|------|
| `ADMIN` | `ELKAZZAZ` | Admin |
| `CONSULTANT` | `ORACLE123` | Consultant |

**Change the ADMIN password from Settings after first login.**

## 🌐 URLs

| URL | Purpose |
|-----|---------|
| `http://localhost:8000/` | SPA (main app) |
| `http://localhost:8000/admin/` | Django Admin (ADMIN only) |
| `http://localhost:8000/api/` | REST API |

## ✨ Features

- 🔐 JWT Auth + Auto-logout (20 min idle)
- 👑 Django Admin Panel (ADMIN only)
- 📁 Multi-format upload: **JSON, CSV, TSV, SQL, Excel (.xlsx/.xls), YAML, XML, HTML, PDF, TXT, ZIP**
- 🗜️ **Gzip compression** on disk (70-90% saving)
- 🚀 **Progress bar** on upload
- 💻 SQL Editor with full SQL support (JOIN, GROUP BY, WHERE, functions)
- 🔍 Real-time search (TABLE_NAME / COLUMN_NAME / Both / All)
- 📊 Search analytics (Top 20 tables)
- 📝 Homepage Notes + Top Tables (Admin-editable)
- 🔒 Access request workflow (Approve / Reject / **Revoke**)
- 👥 Full user management
- 🗑️ Trash (30-day retention)
- 💾 Backup & Restore
- 🔑 API Keys
- 📚 SQL Library (reusable templates)
- 🌗 Dark / Light mode
- 📱 Fully responsive

## 📁 Structure
