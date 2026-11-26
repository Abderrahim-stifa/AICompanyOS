<div align="center">

<img src="assets/aicompanyos-logo.svg" width="116" alt="AICompanyOS robot logo">

# AICompanyOS

### AI Business Operating System

**منصة محلية مفتوحة المصدر لإدارة الأعمال والمهام والعملاء عبر وكلاء قابلين للتشغيل محلياً.**

[![AICompanyOS Build](https://github.com/Abderrahim-stifa/AICompanyOS/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/Abderrahim-stifa/AICompanyOS/actions/workflows/build.yml)
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
- مركز Agent Center يعرض الوكلاء السبعة وحالاتهم وأعداد المهام، إلى جانب مسار pipeline المستقل.
- مركز وكلاء لتشغيل مسار التصنيف والإسناد والمحاسبة.
- إدارة العملاء والمشاريع والمهام.
- تسجيل الدخل والمصروفات وعرض الملخص المالي.
- سجل نشاط للعمليات.
- نسخ احتياطي وإدخال بيانات تجريبية.
- واجهة عربية RTL وسمة ليلية وهوية AICompanyOS.
- واجهة سطر أوامر وJSON API محلية.

## مركز الوكلاء السبعة

تتضمن الواجهة مساحة عمل مستقلة للأدوار السبعة: CEO وResearch وConsultant وEngineer وMarketing وAccountant وMarket Analyst. يختار المستخدم الوكيل ويقدم وصف المهمة، فيرجع الوكيل خطة منظمة وخطوات وأسئلة توضيحية.

**تنبيه تقني:** هذه المرحلة تستخدم قواعد وقوالب محلية قابلة للتشغيل دون إنترنت، وليست وكلاء LLM مستقلة. البحث المباشر، وتوليد الشيفرة، والاتصال بنماذج Ollama أو غيرها تكاملات مستقبلية وليست مفعّلة في هذه النسخة.

اختبارات الوكلاء:
```bash
python -m unittest discover -s tests
```

## الوكلاء

| الوكيل | الوظيفة |
|---|---|
| manager | إدارة المهام وإسنادها للمنفّذ |
| finder | مكوّن البحث عن المهام |
| classifier | تصنيف المهام أو رفض ما يطابق قواعد الحظر |
| executor | الوكيل المنفّذ ضمن دورة العمل |
| accountant | تسجيل دخل المهام المكتملة بعد تأكيد استلام المبلغ |

الوكلاء الحاليون قائمون على قواعد محلية (Rule-based)، وليست نماذج لغوية مستقلة. يظل قرار قبول المهمة وتنفيذها تحت إشراف المستخدم.

## التشغيل على Windows

إذا ظهر الخطأ `'streamlit' is not recognized` رغم تثبيت الحزمة، شغّلها عبر Python مباشرةً:

```bat
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

أو انقر مرتين على الملف `run_windows.bat` الموجود في جذر المشروع. المشغّل يستعمل `python -m streamlit` ولا يعتمد على وجود مجلد Scripts في PATH.

ملاحظة: هذا المستودع يشغّل الواجهة `app.py`. إذا كانت نسختك المحلية تعتمد على `ai_console.py` و`ai_company.py`، فلا تستبدل ملفاتها بهذه النسخة قبل دمج الاختلافات؛ كما أن مجلدك المحلي الذي لا يحتوي على `.git` لا يمكن تحديثه بأمر `git pull`.

## تهيئة قاعدة البيانات v0.1

تُهيّأ قاعدة البيانات تلقائياً عند تشغيل التطبيق، ويمكن تنفيذ التهيئة مستقلةً عبر:

```bash
python -m core.init_db
```

تضيف التهيئة جداول `role_agents` و`settings` و`activity_logs` دون استبدال جدول `agents` الحالي الخاص بوكلاء pipeline الخمسة أو حذف بياناته. تُنشأ `data/settings.json` بالقيم الافتراضية إذا لم تكن موجودة، مع الحفاظ على الملف الموجود.

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
| `core/database.py` | قاعدة بيانات SQLite الأساسية |
| `core/init_db.py` | تهيئة v0.1 الإضافية والبيانات الافتراضية ووظائف الوكلاء وسجل النشاط |
| `core/agent_center.py` | تجميع مؤشرات الوكلاء السبعة |
| `core/agents.py` | قواعد الوكلاء ومسارات التشغيل |
| `core/backup.py` | النسخ الاحتياطي والاستعادة |
| `core/validator.py` | التحقق من المدخلات |
| `core/settings.py` | إعدادات النظام |
| `data/settings.json` | إعدادات العرض واللغة واسم الشركة الافتراضية |
| `ai/` | أصناف الوكلاء السبعة وواجهتهم الموحدة |
| `core/logs.py` | سجلات النشاط والتشغيل |
| `.streamlit/config.toml` | إعدادات المظهر الليلي |

## خارطة الطريق

| الإصدار | النطاق |
|---|---|
| v0.1 | لوحة التحكم ومركز الوكلاء والبنية المحلية |
| v0.2 | إسناد المهام لوكلاء الأدوار وحفظ نتائج التنفيذ |
| v0.3 | CRUD كامل للمهام، الأولوية، وسجل أنشطة النظام |
| v0.4 | تطوير CRM وربط العملاء بالمشاريع والمهام |
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


## إعدادات الوكلاء والواجهة في v0.1

تُخزَّن الوكلاء السبعة في جدول مستقل اسمه `role_agents`، بينما يبقى جدول
`agents` مخصصاً لوكلاء مسار المهام الخمسة الموجودين مسبقاً. التهيئة تراكمية
ويمكن تشغيلها أكثر من مرة دون حذف البيانات:

```bash
python -m core.init_db
python -m streamlit run app.py
```

تُحفظ تفضيلات لوحة التحكم (اسم الشركة، لغة التفضيل، الوضع الليلي، والسمة)
في جدول `settings` داخل SQLite وفي الملف `data/settings.json`. الواجهة
حالياً عربية وبدعم RTL؛ اختيار English يُحفظ كتفضيل، لكن الترجمة الإنجليزية
الكاملة مؤجلة لمرحلة لاحقة. أعداد مهام الوكلاء وحالاتهم وآخر نشاط تُقرأ من
بيانات المهام وسجل النشاط الفعلي.


## v0.2 — Role-agent task engine

The existing `tasks` table and legacy pipeline `agent` field are retained.
An additive migration introduces `role_agent_key`, `result`, `assigned_at`,
and `completed_at`, so tasks can also be assigned to one of the seven
business-role agents without changing the five-agent pipeline.

The Tasks page supports role-agent assignment, lifecycle status updates,
and saving a textual execution report. Saving a report marks the task complete
and writes an event to the existing activity history. This release provides
task orchestration and result persistence; it does not claim autonomous LLM
execution by the seven role agents.


## v0.3 — Task CRUD and system activity history

تدعم قاعدة البيانات إنشاء المهام وقراءتها وتعديلها وحذفها عبر طبقة
`Database` و`Company`. أضيف حقل الأولوية بقيم `low` و`normal`
و`high` و`urgent` عبر ترحيل إضافي يحافظ على المهام الموجودة.

تُسجل عمليات إنشاء المهام وتعديلها وحذفها في جدول `activity_logs`
مع نوع العملية والتفاصيل والتوقيت، وتعرض صفحة **سجل الأنشطة** أحدث
الأحداث أولاً. يبقى جدول `activity` مخصصاً لأحداث الوكلاء ومسار
التنفيذ، ولا يتم استبداله.

اختبارات قاعدة البيانات والإعدادات والسجل معزولة وتستخدم قواعد بيانات
وملفات إعدادات مؤقتة؛ لا تعتمد على وجود بيانات المستخدم المحلية.


## Task management and audit trail

صفحة **المهام** توفر إنشاء المهام وعرضها وتصفيتها وتعديل بياناتها
وأولويتها وحالتها وإسنادها إلى وكيل Pipeline أو وكيل الدور، مع حذف
يتطلب تأكيداً صريحاً.

تُسجل عمليات إنشاء وتعديل وحذف المهمة في `activity_logs` مع
`action` و`entity_type` و`entity_id` و`user_name` والتفاصيل
والتوقيت. يمكن تحديد اسم المشغّل من صفحة المهام. هذا الحقل للتدقيق
التشغيلي فقط؛ لا يمثل نظام مصادقة أو صلاحيات مستخدمين.

تُضاف أعمدة سجل التدقيق بترحيل SQLite إضافي يحافظ على السجلات السابقة.
اختبارات CRUD والتدقيق تستخدم قواعد بيانات مؤقتة ومعزولة.


## v0.3.2 — Dependency injection and repository architecture

تم فصل واجهات الخدمات والمستودعات في `core/services/interfaces.py`، وإضافة
`TaskRepository` كطبقة وصول إلى البيانات فوق `Database` الحالية. تقبل
`TaskService` مستودع المهام ومسجل الأنشطة كاعتماديات قابلة للحقن، مع الحفاظ
على واجهة `Company` الحالية.

تظل كتابة سجل التدقيق لعمليات CRUD داخل معاملات `Database` نفسها لضمان
الاتساق الذري بين تغييرات المهام وسجل الأنشطة. أما `DatabaseActivityLogger`
فيُستخدم كـ adapter قابل للحقن للأحداث الخدمية الأخرى. أضيفت اختبارات
للعقود والحقن وسجل الأنشطة، واستُخدم `st.dialog` لتأكيد حذف المهمة، مع
`notify_and_refresh` لتوحيد رسائل النجاح وإعادة تحميل الواجهة.


## v0.3.4 — Mock tests and audit snapshots

أضيفت اختبارات Mock لعزل `TaskService` والتحقق من تفويض العمليات إلى Repository ومن إمكانية حقن Activity Logger. وسّع مخطط `activity_logs` بإضافة `old_values` و`new_values` عبر ترحيل SQLite إضافي يحافظ على السجلات السابقة. تحفظ عملية تعديل المهمة لقطة الحالة قبل التعديل وبعده داخل نفس transaction التي تحفظ التعديل وسجل التدقيق؛ كما يحتفظ سجل الحذف بلقطة المهمة المحذوفة. واجهة تعديل وحذف المهام وتأكيد الحذف عبر `st.dialog` موجودة في قسم المهام داخل `app.py`.
