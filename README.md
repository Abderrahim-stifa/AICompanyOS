<div align="center">

<img src="assets/aicompanyos-logo.svg" width="116" alt="AICompanyOS robot logo">

# AICompanyOS

### AI Business Operating System

**منصة محلية مفتوحة المصدر لإدارة الأعمال والمهام والعملاء عبر وكلاء قابلين للتشغيل محلياً.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![SQLite](https://img.shields.io/badge/SQLite-Local%20Database-003B57?logo=sqlite&logoColor=white)](https://sqlite.org/)
[![Status](https://img.shields.io/badge/Status-v0.1-ff4d86)](#خارطة-الطريق)
[![Arabic RTL](https://img.shields.io/badge/Interface-Arabic%20RTL-a78bfa)](#المزايا)

</div>

---

## نبذة عن المشروع

AICompanyOS هو نظام مجاني ومفتوح المصدر لإدارة عمليات شركة صغيرة من خلال لوحة عربية موحدة. يضم إدارة العملاء والمشاريع والمهام والحسابات والنسخ الاحتياطي، مع وكلاء قائمين على قواعد محلية وقابلين للتطوير مستقبلاً.

يعتمد التخزين على SQLite، ويمكن تشغيل النظام محلياً دون اشتراكات أو مفاتيح API.

## المزايا الحالية

- لوحة تحكم بمؤشرات العملاء والمشاريع والمهام والوكلاء.
- مركز وكلاء لتشغيل مسار التصنيف والإسناد والمحاسبة.
- إدارة العملاء والمشاريع والمهام.
- تسجيل الدخل والمصروفات وعرض الملخص المالي.
- سجل نشاط للعمليات.
- نسخ احتياطي وإدخال بيانات تجريبية.
- واجهة عربية RTL وسمة ليلية وهوية AICompanyOS.
- واجهة سطر أوامر وJSON API محلية.

## الوكلاء

| الوكيل | الوظيفة |
|---|---|
| manager | إدارة المهام وإسنادها للمنفّذ |
| finder | مكوّن البحث عن المهام |
| classifier | تصنيف المهام أو رفض ما يطابق قواعد الحظر |
| executor | الوكيل المنفّذ ضمن دورة العمل |
| accountant | تسجيل دخل المهام المكتملة بعد تأكيد استلام المبلغ |

الوكلاء الحاليون قائمون على قواعد محلية (Rule-based)، وليست نماذج لغوية مستقلة. يظل قرار قبول المهمة وتنفيذها تحت إشراف المستخدم.

## التشغيل المحلي

يتطلب Python 3.10 أو أحدث.

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

ثم افتح http://localhost:8501.

لإضافة بيانات تجريبية، انتقل إلى **الإعدادات ← إدخال بيانات تجريبية**.

## سطر الأوامر وواجهة JSON API

```bash
python cli.py init
python cli.py add-task "Translate 500 words" --price 5 --source khamsat
python cli.py set-status 1 classified --category translation --agent classifier
python cli.py ledger income 5 --task 1 --note "client payment"
python cli.py summary
python cli.py backup
python cli.py serve
```

تعمل واجهة API على `127.0.0.1:8000`. يتطلب تعريضها لعنوان عام تعيين `AICOS_API_KEY`؛ ويرفض الخادم الربط العام دون مفتاح.

## التقنيات

- Python
- Streamlit
- SQLite
- Pandas
- Plotly

## هيكل المشروع

| المسار | الغرض |
|---|---|
| `app.py` | لوحة Streamlit |
| `cli.py` | سطر الأوامر وHTTP API |
| `core/service.py` | منطق الأعمال المشترك |
| `core/database.py` | قاعدة بيانات SQLite |
| `core/agents.py` | قواعد الوكلاء ومسارات التشغيل |
| `core/backup.py` | النسخ الاحتياطي والاستعادة |
| `core/validator.py` | التحقق من المدخلات |
| `core/settings.py` | إعدادات النظام |
| `core/logs.py` | سجلات النشاط والتشغيل |
| `.streamlit/config.toml` | إعدادات المظهر الليلي |

## خارطة الطريق

| الإصدار | النطاق |
|---|---|
| v0.1 | لوحة التحكم ومركز الوكلاء والبنية المحلية |
| v0.2 | توسيع إدارة المهام وتدفقات الوكلاء |
| v0.3 | تطوير CRM وإدارة المشاريع |
| v0.4 | التقارير والإحصائيات |
| v0.5 | المحاسبة الأساسية |
| v1.0 | الاستقرار وإدارة المستخدمين والنسخ الاحتياطي وسجلات النشاط |
| v2.0 | تكامل Ollama وQwen ووكلاء LLM محليين |

## الهوية البصرية

تعتمد الواجهة على خلفية داكنة مع تدرجات وردية وبنفسجية ولمسات ذهبية، وشعار روبوت مخصص. تُستخدم الهوية في رأس لوحة التحكم وملف README.

## الترخيص

لم نعثر في الملفات الحالية على ملف LICENSE يحدد ترخيصاً قانونياً. أضف ملف LICENSE واختيار الترخيص المناسب قبل وصف المشروع بأنه MIT أو غيره.

---

<div align="center">

**AICompanyOS — Build your company, locally.**

</div>
