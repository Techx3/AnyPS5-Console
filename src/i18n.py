import re

UI_LANGUAGES = [("en", "English"), ("zh", "中文 (简体)"), ("hi", "हिन्दी"), ("es", "Español"), ("fr", "Français"),
                ("ar", "العربية")]
LANG_ORDER = ("en", "zh", "hi", "fr", "ar")
RTL = {"ar"}
SCRIPT = {"ar": "Arab", "hi": "Deva", "zh": "Hans"}
FONTS = {
    "cjk": "microsoftyaheiui,notosanscjksc,simhei,arial",
    "deva": "notosansdevanagari,nirmalaui,mangal,aparajita,arial",
    "arab": "notosansarabic,segoeui,tahoma,arial",
}
DEFAULT_FONTS = "microsoftyaheiui,yugothicui,segoeui,arial"


def script_of(ch):
    o = ord(ch)
    if 0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F or 0xFB50 <= o <= 0xFEFF:
        return "arab"
    if 0x0900 <= o <= 0x097F:
        return "deva"
    if 0x3000 <= o <= 0x9FFF or 0xAC00 <= o <= 0xD7AF or 0xFF00 <= o <= 0xFFEF:
        return "cjk"
    if ch.isalnum():
        return "latin"
    return None


MIRROR = str.maketrans("()[]{}<>", ")(][}{><")


def runs(text):
    out = []
    rtl = any(script_of(ch) == "arab" for ch in text)
    for ch in text:
        sc = script_of(ch)
        if sc is None and not ch.isspace():
            sc = "latin"
            if rtl:
                ch = ch.translate(MIRROR)
        if out and (sc is None or sc == out[-1][0]):
            out[-1][1] += ch
        else:
            out.append([sc or "latin", ch])
    return [(a, b) for a, b in out]

GAME_LANGUAGES = [
    (0, "日本語"), (1, "English (US)"), (2, "Français"), (3, "Español (España)"), (4, "Deutsch"), (5, "Italiano"),
    (6, "Nederlands"), (7, "Português (Portugal)"), (8, "Русский"), (9, "한국어"), (10, "中文 (繁體)"),
    (11, "中文 (简体)"), (12, "Suomi"), (13, "Svenska"), (14, "Dansk"), (15, "Norsk"), (16, "Polski"),
    (17, "Português (Brasil)"), (18, "English (UK)"), (19, "Türkçe"), (20, "Español (Latinoamérica)"),
    (21, "العربية"), (22, "Français (Canada)"), (23, "Čeština"), (24, "Magyar"), (25, "Ελληνικά"),
    (26, "Română"), (27, "ไทย"), (28, "Tiếng Việt"), (29, "Bahasa Indonesia"), (30, "Українська"),
]
DEFAULT_GAME_LANGUAGE = {"en": 1, "zh": 11, "hi": 1, "es": 20, "fr": 2, "ar": 21}

T = [
    # es, en, zh, hi, fr, ar
    ("Sí", "Yes", "是", "हाँ", "Oui", "نعم"),
    ("No", "No", "否", "नहीं", "Non", "لا"),
    ("Menú", "Menu", "菜单", "मेनू", "Menu", "القائمة"),
    ("Jugar", "Play", "开始游戏", "खेलें", "Jouer", "تشغيل"),
    ("Opciones", "Options", "选项", "विकल्प", "Options", "خيارات"),
    ("Recargar", "Refresh", "刷新", "रीफ़्रेश", "Actualiser", "تحديث"),
    ("Elegir", "Select", "选择", "चुनें", "Choisir", "اختيار"),
    ("Volver", "Back", "返回", "वापस", "Retour", "رجوع"),
    ("Escribir", "Type", "输入", "लिखें", "Écrire", "كتابة"),
    ("Borrar", "Delete", "删除", "मिटाएँ", "Effacer", "حذف"),
    ("Espacio", "Space", "空格", "स्पेस", "Espace", "مسافة"),
    ("Listo", "Done", "完成", "हो गया", "Terminé", "تم"),
    ("Cancelar", "Cancel", "取消", "रद्द करें", "Annuler", "إلغاء"),
    ("Pegar", "Paste", "粘贴", "पेस्ट", "Coller", "لصق"),
    ("Aceptar", "OK", "确定", "ठीक है", "OK", "موافق"),
    ("Desplazar", "Scroll", "滚动", "स्क्रॉल", "Défiler", "تمرير"),
    ("Cerrar", "Close", "关闭", "बंद करें", "Fermer", "إغلاق"),
    ("Salir", "Quit", "退出", "बाहर निकलें", "Quitter", "خروج"),
    ("Ajustes", "Settings", "设置", "सेटिंग्स", "Paramètres", "الإعدادات"),
    ("Actualizaciones", "Updates", "更新", "अपडेट", "Mises à jour", "التحديثات"),
    ("Error", "Error", "错误", "त्रुटि", "Erreur", "خطأ"),
    ("Repositorio", "Repository", "仓库", "रिपॉज़िटरी", "Dépôt", "المستودع"),
    ("Estable", "Stable", "稳定版", "स्थिर", "Stable", "مستقر"),
    ("Repositorio (main)", "Repository (main)", "仓库 (main)", "रिपॉज़िटरी (main)", "Dépôt (main)", "المستودع (main)"),
    ("Estable (release)", "Stable (release)", "稳定版 (release)", "स्थिर (release)", "Stable (release)", "مستقر (release)"),
    ("EN USO", "IN USE", "使用中", "उपयोग में", "UTILISÉ", "قيد الاستخدام"),
    ("Comprobando...", "Checking...", "正在检查...", "जाँच हो रही है...", "Vérification...", "جارٍ التحقق..."),
    ("Listo", "Done", "完成", "हो गया", "Terminé", "تم"),
    ("Sin convertir", "Not converted", "未转换", "परिवर्तित नहीं", "Non converti", "غير محوّل"),
    ("Desactualizado", "Outdated", "已过期", "पुराना", "Obsolète", "قديم"),
    ("Sin relinker", "No relinker", "没有 relinker", "relinker नहीं", "Pas de relinker", "لا يوجد relinker"),
    ("Sin versión estable", "No stable version", "无稳定版", "स्थिर संस्करण नहीं", "Pas de version stable", "لا توجد نسخة مستقرة"),
    ("Actualización disponible", "Update available", "有可用更新", "अपडेट उपलब्ध", "Mise à jour disponible", "تحديث متاح"),
    ("Al día", "Up to date", "已是最新", "अद्यतन", "À jour", "محدّث"),
    ("Sin conexión", "Offline", "离线", "ऑफ़लाइन", "Hors ligne", "غير متصل"),
    ("no instalada", "not installed", "未安装", "स्थापित नहीं", "non installée", "غير مثبتة"),
    ("(sin elegir)", "(not set)", "(未设置)", "(सेट नहीं)", "(non défini)", "(غير محدد)"),
    ("AnyPS5 Console es un proyecto personal. Haz pausas cuando juegues por mucho tiempo.",
     "AnyPS5 Console is a personal project. Take breaks when you play for a long time.",
     "AnyPS5 Console 是个人项目。长时间游戏时请适当休息。",
     "AnyPS5 Console एक निजी प्रोजेक्ट है। लंबे समय तक खेलते समय ब्रेक लें।",
     "AnyPS5 Console est un projet personnel. Faites des pauses quand vous jouez longtemps.",
     "AnyPS5 Console مشروع شخصي. خذ فترات راحة عند اللعب لفترة طويلة."),
    ("AnyPS5 actualizado desde el repositorio.", "AnyPS5 updated from the repository.", "已从仓库更新 AnyPS5。",
     "AnyPS5 रिपॉज़िटरी से अपडेट हुआ।", "AnyPS5 mis à jour depuis le dépôt.", "تم تحديث AnyPS5 من المستودع."),
    ("Abrir carpeta (audit.txt)", "Open folder (audit.txt)", "打开文件夹 (audit.txt)", "फ़ोल्डर खोलें (audit.txt)",
     "Ouvrir le dossier (audit.txt)", "فتح المجلد (audit.txt)"),
    ("Abrir carpeta convertida", "Open converted folder", "打开转换文件夹", "परिवर्तित फ़ोल्डर खोलें",
     "Ouvrir le dossier converti", "فتح المجلد المحوّل"),
    ("Abrir carpeta del juego", "Open game folder", "打开游戏文件夹", "गेम फ़ोल्डर खोलें", "Ouvrir le dossier du jeu",
     "فتح مجلد اللعبة"),
    ("Abrir carpeta del log", "Open log folder", "打开日志文件夹", "लॉग फ़ोल्डर खोलें", "Ouvrir le dossier du journal",
     "فتح مجلد السجل"),
    ("Actualizando AnyPS5 (repositorio)", "Updating AnyPS5 (repository)", "正在更新 AnyPS5 (仓库)",
     "AnyPS5 अपडेट हो रहा है (रिपॉज़िटरी)", "Mise à jour d'AnyPS5 (dépôt)", "جارٍ تحديث AnyPS5 (المستودع)"),
    ("Actualizar desde el repositorio y compilar", "Update from the repository and build", "从仓库更新并编译",
     "रिपॉज़िटरी से अपडेट करें और बिल्ड करें", "Mettre à jour depuis le dépôt et compiler", "التحديث من المستودع والبناء"),
    ("Actualizar y compilar", "Update and build", "更新并编译", "अपडेट और बिल्ड करें", "Mettre à jour et compiler",
     "التحديث والبناء"),
    ("Clonar y compilar", "Clone and build", "克隆并编译", "क्लोन और बिल्ड करें", "Cloner et compiler", "استنساخ وبناء"),
    ("Añadir carpeta de juegos PC", "Add PC games folder", "添加 PC 游戏文件夹", "PC गेम फ़ोल्डर जोड़ें",
     "Ajouter un dossier de jeux PC", "إضافة مجلد ألعاب الكمبيوتر"),
    ("Añadir fork (enlace de GitHub)", "Add fork (GitHub link)", "添加 fork (GitHub 链接)", "fork जोड़ें (GitHub लिंक)",
     "Ajouter un fork (lien GitHub)", "إضافة fork (رابط GitHub)"),
    ("Añadir fork de AnyPS5", "Add an AnyPS5 fork", "添加 AnyPS5 fork", "AnyPS5 fork जोड़ें", "Ajouter un fork d'AnyPS5",
     "إضافة fork لـ AnyPS5"),
    ("Añadir un ejecutable (.exe)", "Add an executable (.exe)", "添加可执行文件 (.exe)", "एक्ज़ीक्यूटेबल जोड़ें (.exe)",
     "Ajouter un exécutable (.exe)", "إضافة ملف تنفيذي (.exe)"),
    ("Buscar actualizaciones al iniciar", "Check for updates at startup", "启动时检查更新", "शुरू होने पर अपडेट जाँचें",
     "Rechercher des mises à jour au démarrage", "التحقق من التحديثات عند البدء"),
    ("Buscar de nuevo", "Check again", "再次检查", "फिर से जाँचें", "Vérifier à nouveau", "التحقق مرة أخرى"),
    ("Cambiar de usuario", "Switch user", "切换用户", "उपयोगकर्ता बदलें", "Changer d'utilisateur", "تبديل المستخدم"),
    ("Cargando juego…", "Loading game…", "正在加载游戏…", "गेम लोड हो रहा है…", "Chargement du jeu…", "جارٍ تحميل اللعبة…"),
    ("Carpeta de juegos PC", "PC games folder", "PC 游戏文件夹", "PC गेम फ़ोल्डर", "Dossier des jeux PC", "مجلد ألعاب الكمبيوتر"),
    ("Carpeta de juegos PS5", "PS5 games folder", "PS5 游戏文件夹", "PS5 गेम फ़ोल्डर", "Dossier des jeux PS5", "مجلد ألعاب PS5"),
    ("Crear usuario", "Create user", "创建用户", "उपयोगकर्ता बनाएँ", "Créer un utilisateur", "إنشاء مستخدم"),
    ("Detectar juegos de Epic Games", "Detect Epic Games library", "检测 Epic Games 游戏库", "Epic Games लाइब्रेरी खोजें",
     "Détecter la bibliothèque Epic Games", "اكتشاف مكتبة Epic Games"),
    ("Detectar juegos de Steam", "Detect Steam library", "检测 Steam 游戏库", "Steam लाइब्रेरी खोजें",
     "Détecter la bibliothèque Steam", "اكتشاف مكتبة Steam"),
    ("Ejecutable del juego", "Game executable", "游戏可执行文件", "गेम एक्ज़ीक्यूटेबल", "Exécutable du jeu", "الملف التنفيذي للعبة"),
    ("El juego no puede cargar: le faltan funciones que AnyPS5 aún no tiene.",
     "The game cannot load: it needs functions AnyPS5 does not have yet.",
     "游戏无法加载：缺少 AnyPS5 尚未实现的函数。",
     "गेम लोड नहीं हो सकता: इसे ऐसे फ़ंक्शन चाहिए जो AnyPS5 में अभी नहीं हैं।",
     "Le jeu ne peut pas se charger : il lui manque des fonctions qu'AnyPS5 n'a pas encore.",
     "لا يمكن تحميل اللعبة: تحتاج إلى دوال لا يملكها AnyPS5 بعد."),
    ("Elige la carpeta de juegos PS5 en Menú > Ajustes", "Choose the PS5 games folder in Menu > Settings",
     "请在 菜单 > 设置 中选择 PS5 游戏文件夹", "मेनू > सेटिंग्स में PS5 गेम फ़ोल्डर चुनें",
     "Choisissez le dossier des jeux PS5 dans Menu > Paramètres", "اختر مجلد ألعاب PS5 من القائمة > الإعدادات"),
    ("Eliminar usuario (los saves se conservan)", "Delete user (saves are kept)", "删除用户（保留存档）",
     "उपयोगकर्ता हटाएँ (सेव रखे जाएँगे)", "Supprimer l'utilisateur (les sauvegardes sont conservées)",
     "حذف المستخدم (يتم الاحتفاظ بالحفظ)"),
    ("En juego · cierra el juego para volver", "Playing · close the game to come back", "游戏中 · 关闭游戏即可返回",
     "खेल रहे हैं · वापस आने के लिए गेम बंद करें", "En jeu · fermez le jeu pour revenir", "قيد اللعب · أغلق اللعبة للعودة"),
    ("Enlace del repositorio. Para una rama: …/tree/rama o enlace#rama",
     "Repository link. For a branch: …/tree/branch or link#branch", "仓库链接。指定分支：…/tree/分支 或 链接#分支",
     "रिपॉज़िटरी लिंक। किसी ब्रांच के लिए: …/tree/branch या link#branch",
     "Lien du dépôt. Pour une branche : …/tree/branche ou lien#branche",
     "رابط المستودع. لفرع معيّن: …/tree/الفرع أو الرابط#الفرع"),
    ("Escribe un nombre", "Type a name", "请输入名称", "कोई नाम लिखें", "Saisissez un nom", "اكتب اسمًا"),
    ("Funciones del sistema (qué le falta)", "System functions (what is missing)", "系统函数（缺少什么）",
     "सिस्टम फ़ंक्शन (क्या कमी है)", "Fonctions système (ce qui manque)", "دوال النظام (ما الذي ينقص)"),
    ("Instalando versión estable", "Installing stable version", "正在安装稳定版", "स्थिर संस्करण स्थापित हो रहा है",
     "Installation de la version stable", "جارٍ تثبيت النسخة المستقرة"),
    ("Instalar la versión estable", "Install the stable version", "安装稳定版", "स्थिर संस्करण स्थापित करें",
     "Installer la version stable", "تثبيت النسخة المستقرة"),
    ("Juegos PC", "PC games", "PC 游戏", "PC गेम", "Jeux PC", "ألعاب الكمبيوتر"),
    ("Juegos PS5", "PS5 games", "PS5 游戏", "PS5 गेम", "Jeux PS5", "ألعاب PS5"),
    ("Juegos PC (carpetas y ejecutables)", "PC games (folders and executables)", "PC 游戏（文件夹和可执行文件）",
     "PC गेम (फ़ोल्डर और एक्ज़ीक्यूटेबल)", "Jeux PC (dossiers et exécutables)", "ألعاب الكمبيوتر (مجلدات وملفات تنفيذية)"),
    ("Juegos en pantalla completa", "Games in fullscreen", "游戏全屏", "गेम फ़ुलस्क्रीन में", "Jeux en plein écran",
     "الألعاب بملء الشاشة"),
    ("Jugar igual", "Play anyway", "仍然开始", "फिर भी खेलें", "Jouer quand même", "تشغيل على أي حال"),
    ("Mostrar juegos ocultos", "Show hidden games", "显示隐藏的游戏", "छिपे गेम दिखाएँ", "Afficher les jeux masqués",
     "إظهار الألعاب المخفية"),
    ("No falta nada: todas las funciones que usa el juego existen en esta versión.",
     "Nothing is missing: every function the game uses exists in this version.",
     "没有缺失：游戏使用的所有函数在此版本中都存在。",
     "कुछ भी कम नहीं: गेम जो भी फ़ंक्शन उपयोग करता है, वे इस संस्करण में मौजूद हैं।",
     "Rien ne manque : toutes les fonctions utilisées par le jeu existent dans cette version.",
     "لا ينقص شيء: كل الدوال التي تستخدمها اللعبة موجودة في هذه النسخة."),
    ("No hay versión estable instalada. Ve a Actualizaciones.", "No stable version installed. Go to Updates.",
     "未安装稳定版。请前往“更新”。", "कोई स्थिर संस्करण स्थापित नहीं है। अपडेट में जाएँ।",
     "Aucune version stable installée. Allez dans Mises à jour.", "لا توجد نسخة مستقرة مثبتة. انتقل إلى التحديثات."),
    ("No se pudo revisar: la versión de AnyPS5 en uso no genera el registro (--registry).",
     "Could not check: the AnyPS5 version in use does not write the registry (--registry).",
     "无法检查：当前使用的 AnyPS5 版本不生成注册表 (--registry)。",
     "जाँच नहीं हो सकी: उपयोग में AnyPS5 संस्करण रजिस्ट्री (--registry) नहीं लिखता।",
     "Vérification impossible : la version d'AnyPS5 utilisée n'écrit pas le registre (--registry).",
     "تعذّر التحقق: نسخة AnyPS5 المستخدمة لا تكتب السجل (--registry)."),
    ("Nuevo usuario", "New user", "新用户", "नया उपयोगकर्ता", "Nouvel utilisateur", "مستخدم جديد"),
    ("Ocultar de la lista", "Hide from the list", "从列表中隐藏", "सूची से छिपाएँ", "Masquer de la liste", "إخفاء من القائمة"),
    ("Pantalla completa (consola)", "Fullscreen (console)", "全屏（主机界面）", "फ़ुलस्क्रीन (कंसोल)",
     "Plein écran (console)", "ملء الشاشة (الواجهة)"),
    ("Pantalla completa", "Fullscreen", "全屏", "फ़ुलस्क्रीन", "Plein écran", "ملء الشاشة"),
    ("Pulsa cualquier botón del control", "Press any button", "按任意键", "कोई भी बटन दबाएँ", "Appuyez sur un bouton",
     "اضغط على أي زر"),
    ("Quitar de la lista", "Remove from the list", "从列表中移除", "सूची से हटाएँ", "Retirer de la liste", "إزالة من القائمة"),
    ("Quitar y borrar sus archivos", "Remove and delete its files", "移除并删除其文件", "हटाएँ और इसकी फ़ाइलें मिटाएँ",
     "Retirer et supprimer ses fichiers", "إزالة وحذف ملفاته"),
    ("Recargar juegos", "Reload games", "重新加载游戏", "गेम फिर से लोड करें", "Recharger les jeux", "إعادة تحميل الألعاب"),
    ("Reconvertir y jugar", "Reconvert and play", "重新转换并开始", "फिर से परिवर्तित करें और खेलें", "Reconvertir et jouer",
     "إعادة التحويل والتشغيل"),
    ("Revisando funciones del sistema que usa el juego...", "Checking the system functions the game uses...",
     "正在检查游戏使用的系统函数...", "गेम द्वारा उपयोग किए गए सिस्टम फ़ंक्शन जाँचे जा रहे हैं...",
     "Vérification des fonctions système utilisées par le jeu...", "جارٍ فحص دوال النظام التي تستخدمها اللعبة..."),
    ("Sin juegos de PC: Menú > Ajustes > Juegos PC", "No PC games: Menu > Settings > PC games",
     "没有 PC 游戏：菜单 > 设置 > PC 游戏", "कोई PC गेम नहीं: मेनू > सेटिंग्स > PC गेम",
     "Aucun jeu PC : Menu > Paramètres > Jeux PC", "لا توجد ألعاب كمبيوتر: القائمة > الإعدادات > ألعاب الكمبيوتر"),
    ("Usar esta versión", "Use this version", "使用此版本", "यह संस्करण उपयोग करें", "Utiliser cette version",
     "استخدام هذه النسخة"),
    ("Versión de AnyPS5", "AnyPS5 version", "AnyPS5 版本", "AnyPS5 संस्करण", "Version d'AnyPS5", "نسخة AnyPS5"),
    ("librería sin nombre", "unnamed library", "未命名库", "बिना नाम की लाइब्रेरी", "bibliothèque sans nom", "مكتبة بلا اسم"),
    ("¿Quién está usando el control?", "Who's using the controller?", "谁在使用手柄？", "कंट्रोलर कौन उपयोग कर रहा है?",
     "Qui utilise la manette ?", "من يستخدم وحدة التحكم؟"),
    ("funciones completas", "all functions present", "函数齐全", "सभी फ़ंक्शन मौजूद", "toutes les fonctions présentes",
     "كل الدوال موجودة"),
    ("AUSENTE", "MISSING", "缺失", "अनुपस्थित", "ABSENTE", "مفقودة"),
    ("STUB", "STUB", "桩函数", "STUB", "STUB", "STUB"),
    ("Idioma", "Language", "语言", "भाषा", "Langue", "اللغة"),
    ("Idioma de los juegos", "Game language", "游戏语言", "गेम की भाषा", "Langue des jeux", "لغة الألعاب"),
    ("Igual que la consola", "Same as the console", "与主机相同", "कंसोल जैसी", "Comme la console", "مثل الواجهة"),
    ("Ya convertido: se omite la conversion.", "Already converted: skipping conversion.", "已转换：跳过转换。",
     "पहले से परिवर्तित: रूपांतरण छोड़ा गया।", "Déjà converti : conversion ignorée.", "تم التحويل مسبقًا: تخطي التحويل."),
    ("Conversion terminada.", "Conversion done.", "转换完成。", "रूपांतरण पूरा।", "Conversion terminée.", "اكتمل التحويل."),
    ("Extrayendo ELF del SELF de eboot...", "Extracting the ELF from the eboot SELF...", "正在从 eboot SELF 提取 ELF...",
     "eboot SELF से ELF निकाला जा रहा है...", "Extraction de l'ELF du SELF eboot...", "جارٍ استخراج ELF من SELF الخاص بـ eboot..."),
    ("AnyPS5 compilado.", "AnyPS5 built.", "AnyPS5 编译完成。", "AnyPS5 बिल्ड हो गया।", "AnyPS5 compilé.", "تم بناء AnyPS5."),
    ("Descargando cambios de origin/main...", "Downloading changes from origin/main...", "正在下载 origin/main 的更改...",
     "origin/main से बदलाव डाउनलोड हो रहे हैं...", "Téléchargement des modifications d'origin/main...",
     "جارٍ تنزيل التغييرات من origin/main..."),
    ("Fusión lista.", "Merge done.", "合并完成。", "मर्ज पूरा।", "Fusion terminée.", "اكتمل الدمج."),
    ("Extrayendo librerias...", "Extracting libraries...", "正在解压库...", "लाइब्रेरी निकाली जा रही हैं...",
     "Extraction des bibliothèques...", "جارٍ استخراج المكتبات..."),
    ("Descargando cambios del fork...", "Downloading fork changes...", "正在下载 fork 的更改...",
     "fork के बदलाव डाउनलोड हो रहे हैं...", "Téléchargement des modifications du fork...", "جارٍ تنزيل تغييرات fork..."),
    ("Saves existentes movidos al usuario.", "Existing saves moved to the user.", "已将现有存档移至该用户。",
     "मौजूदा सेव उपयोगकर्ता में ले जाए गए।", "Sauvegardes existantes déplacées vers l'utilisateur.",
     "تم نقل الحفظ الموجود إلى المستخدم."),
    ("Recompilando AnyPS5 (rebuild.flag)...", "Rebuilding AnyPS5 (rebuild.flag)...", "正在重新编译 AnyPS5 (rebuild.flag)...",
     "AnyPS5 फिर से बिल्ड हो रहा है (rebuild.flag)...", "Recompilation d'AnyPS5 (rebuild.flag)...",
     "جارٍ إعادة بناء AnyPS5 (rebuild.flag)..."),
    ("Faltan herramientas de compilación (Git y MinGW). Instálalas en Actualizaciones.",
     "Build tools are missing (Git and MinGW). Install them in Updates.", "缺少编译工具（Git 和 MinGW）。请在“更新”中安装。",
     "बिल्ड टूल (Git और MinGW) नहीं हैं। उन्हें अपडेट में स्थापित करें।",
     "Les outils de compilation manquent (Git et MinGW). Installez-les dans Mises à jour.",
     "أدوات البناء مفقودة (Git و MinGW). ثبّتها من التحديثات."),
    ("Herramientas de compilación instaladas.", "Build tools installed.", "编译工具已安装。", "बिल्ड टूल स्थापित हो गए।",
     "Outils de compilation installés.", "تم تثبيت أدوات البناء."),
    ("Instalar herramientas de compilación (Git + MinGW)", "Install build tools (Git + MinGW)", "安装编译工具（Git + MinGW）",
     "बिल्ड टूल स्थापित करें (Git + MinGW)", "Installer les outils de compilation (Git + MinGW)", "تثبيت أدوات البناء (Git + MinGW)"),
    ("Instalando herramientas de compilación", "Installing build tools", "正在安装编译工具", "बिल्ड टूल स्थापित हो रहे हैं",
     "Installation des outils de compilation", "جارٍ تثبيت أدوات البناء"),
]

PATTERNS = [
    # regex on the Spanish text, templates per language, groups to translate recursively
    (r"Preparando (.+?) \((.+)\)", {"en": "Preparing {1} ({2})", "zh": "正在准备 {1} ({2})", "hi": "{1} तैयार हो रहा है ({2})",
                                     "fr": "Préparation de {1} ({2})", "ar": "جارٍ تجهيز {1} ({2})"}, (2,)),
    (r"Preparando (.+)", {"en": "Preparing {1}", "zh": "正在准备 {1}", "hi": "{1} तैयार हो रहा है", "fr": "Préparation de {1}",
                          "ar": "جارٍ تجهيز {1}"}, ()),
    (r"Abriendo (.+) en (.+)\.\.\.", {"en": "Opening {1} in {2}...", "zh": "正在通过 {2} 打开 {1}...",
                                      "hi": "{1} को {2} में खोला जा रहा है...", "fr": "Ouverture de {1} dans {2}...",
                                      "ar": "جارٍ فتح {1} في {2}..."}, ()),
    (r"El fork (.+) ya está en la lista", {"en": "The fork {1} is already in the list", "zh": "fork {1} 已在列表中",
                                           "hi": "fork {1} पहले से सूची में है", "fr": "Le fork {1} est déjà dans la liste",
                                           "ar": "fork {1} موجود بالفعل في القائمة"}, ()),
    (r"El juego terminó con codigo (.+)", {"en": "The game exited with code {1}", "zh": "游戏已退出，代码 {1}",
                                           "hi": "गेम कोड {1} के साथ बंद हुआ", "fr": "Le jeu s'est arrêté avec le code {1}",
                                           "ar": "انتهت اللعبة بالرمز {1}"}, ()),
    (r"Fork (.+) listo\.", {"en": "Fork {1} ready.", "zh": "Fork {1} 已就绪。", "hi": "Fork {1} तैयार है।",
                            "fr": "Fork {1} prêt.", "ar": "Fork {1} جاهز."}, ()),
    (r"Fork (.+) quitado\.", {"en": "Fork {1} removed.", "zh": "已移除 Fork {1}。", "hi": "Fork {1} हटाया गया।",
                              "fr": "Fork {1} retiré.", "ar": "تمت إزالة Fork {1}."}, ()),
    (r"Funciones del sistema · (.*)", {"en": "System functions · {1}", "zh": "系统函数 · {1}", "hi": "सिस्टम फ़ंक्शन · {1}",
                                       "fr": "Fonctions système · {1}", "ar": "دوال النظام · {1}"}, ()),
    (r"Instalando fork (.+)", {"en": "Installing fork {1}", "zh": "正在安装 fork {1}", "hi": "fork {1} स्थापित हो रहा है",
                               "fr": "Installation du fork {1}", "ar": "جارٍ تثبيت fork {1}"}, ()),
    (r"Juegos PC  ·  (\d+)", {"en": "PC games  ·  {1}", "zh": "PC 游戏  ·  {1}", "hi": "PC गेम  ·  {1}",
                              "fr": "Jeux PC  ·  {1}", "ar": "ألعاب الكمبيوتر  ·  {1}"}, ()),
    (r"Juegos PS5  ·  (\d+)", {"en": "PS5 games  ·  {1}", "zh": "PS5 游戏  ·  {1}", "hi": "PS5 गेम  ·  {1}",
                               "fr": "Jeux PS5  ·  {1}", "ar": "ألعاب PS5  ·  {1}"}, ()),
    (r"([▲▼] )(.+)", {"*": "{1}{2}"}, (2,)),
    (r"Jugar con (.+)", {"en": "Play with {1}", "zh": "使用 {1} 开始", "hi": "{1} के साथ खेलें", "fr": "Jouer avec {1}",
                         "ar": "تشغيل باستخدام {1}"}, (1,)),
    (r"La versión (.+) no está instalada\.", {"en": "The {1} version is not installed.", "zh": "{1} 版本未安装。",
                                              "hi": "{1} संस्करण स्थापित नहीं है।", "fr": "La version {1} n'est pas installée.",
                                              "ar": "النسخة {1} غير مثبتة."}, (1,)),
    (r"(.+) no está instalada\. Instálala en Actualizaciones\.",
     {"en": "{1} is not installed. Install it in Updates.", "zh": "{1} 未安装。请在“更新”中安装。",
      "hi": "{1} स्थापित नहीं है। इसे अपडेट में स्थापित करें।", "fr": "{1} n'est pas installée. Installez-la dans Mises à jour.",
      "ar": "{1} غير مثبتة. ثبّتها من التحديثات."}, (1,)),
    (r"No se pudo abrir (.+?): (.+)", {"en": "Could not open {1}: {2}", "zh": "无法打开 {1}：{2}",
                                       "hi": "{1} नहीं खुल सका: {2}", "fr": "Impossible d'ouvrir {1} : {2}",
                                       "ar": "تعذّر فتح {1}: {2}"}, ()),
    (r"Primer bloqueo: (.+)", {"en": "First blocker: {1}", "zh": "首个阻塞：{1}", "hi": "पहली रुकावट: {1}",
                               "fr": "Premier blocage : {1}", "ar": "أول عائق: {1}"}, ()),
    (r"Quitar carpeta: (.+)", {"en": "Remove folder: {1}", "zh": "移除文件夹：{1}", "hi": "फ़ोल्डर हटाएँ: {1}",
                               "fr": "Retirer le dossier : {1}", "ar": "إزالة المجلد: {1}"}, ()),
    (r"Revisando funciones de (.+)", {"en": "Checking functions of {1}", "zh": "正在检查 {1} 的函数",
                                      "hi": "{1} के फ़ंक्शन जाँचे जा रहे हैं", "fr": "Vérification des fonctions de {1}",
                                      "ar": "جارٍ فحص دوال {1}"}, ()),
    (r"Usando (.+)", {"en": "Using {1}", "zh": "正在使用 {1}", "hi": "{1} उपयोग में", "fr": "Utilisation de {1}",
                      "ar": "يتم استخدام {1}"}, (1,)),
    (r"Usar versión: (.+)", {"en": "Use version: {1}", "zh": "使用版本：{1}", "hi": "संस्करण उपयोग करें: {1}",
                             "fr": "Utiliser la version : {1}", "ar": "استخدام النسخة: {1}"}, (1,)),
    (r"Usar (.+)", {"en": "Use {1}", "zh": "使用 {1}", "hi": "{1} उपयोग करें", "fr": "Utiliser {1}", "ar": "استخدام {1}"}, (1,)),
    (r"Usuario (.+) creado", {"en": "User {1} created", "zh": "已创建用户 {1}", "hi": "उपयोगकर्ता {1} बनाया गया",
                              "fr": "Utilisateur {1} créé", "ar": "تم إنشاء المستخدم {1}"}, ()),
    (r"Versión estable (.+) instalada\.", {"en": "Stable version {1} installed.", "zh": "已安装稳定版 {1}。",
                                           "hi": "स्थिर संस्करण {1} स्थापित हुआ।", "fr": "Version stable {1} installée.",
                                           "ar": "تم تثبيت النسخة المستقرة {1}."}, ()),
    (r"local (.+)  ·  disponible (.+)", {"en": "local {1}  ·  available {2}", "zh": "本地 {1}  ·  可用 {2}",
                                          "hi": "लोकल {1}  ·  उपलब्ध {2}", "fr": "local {1}  ·  disponible {2}",
                                          "ar": "محلي {1}  ·  متاح {2}"}, ()),
    (r"le faltan (\d+) funciones", {"en": "missing {1} functions", "zh": "缺少 {1} 个函数", "hi": "{1} फ़ंक्शन कम हैं",
                                    "fr": "il manque {1} fonctions", "ar": "تنقصها {1} دوال"}, ()),
    (r"(\d+) funciones incompletas", {"en": "{1} incomplete functions", "zh": "{1} 个函数不完整", "hi": "{1} अधूरे फ़ंक्शन",
                                      "fr": "{1} fonctions incomplètes", "ar": "{1} دوال غير مكتملة"}, ()),
    (r"(\d+) ausentes", {"en": "{1} missing", "zh": "{1} 个缺失", "hi": "{1} अनुपस्थित", "fr": "{1} absentes",
                         "ar": "{1} مفقودة"}, ()),
    (r"(\d+) implementadas", {"en": "{1} implemented", "zh": "{1} 个已实现", "hi": "{1} लागू", "fr": "{1} implémentées",
                              "ar": "{1} منفّذة"}, ()),
    (r"(\d+) incompletas \(stub\)", {"en": "{1} incomplete (stub)", "zh": "{1} 个不完整 (stub)", "hi": "{1} अधूरे (stub)",
                                     "fr": "{1} incomplètes (stub)", "ar": "{1} غير مكتملة (stub)"}, ()),
    (r"(\d+) librerías faltantes", {"en": "{1} missing libraries", "zh": "缺少 {1} 个库", "hi": "{1} लाइब्रेरी कम हैं",
                                    "fr": "{1} bibliothèques manquantes", "ar": "{1} مكتبات مفقودة"}, ()),
    (r"(\d+) carpetas, (\d+) exe", {"en": "{1} folders, {2} exe", "zh": "{1} 个文件夹，{2} 个 exe",
                                    "hi": "{1} फ़ोल्डर, {2} exe", "fr": "{1} dossiers, {2} exe", "ar": "{1} مجلدات، {2} exe"}, ()),
    (r"Actualización disponible: (.+)  ·  Menú > Actualizaciones",
     {"en": "Update available: {1}  ·  Menu > Updates", "zh": "有可用更新：{1}  ·  菜单 > 更新",
      "hi": "अपडेट उपलब्ध: {1}  ·  मेनू > अपडेट", "fr": "Mise à jour disponible : {1}  ·  Menu > Mises à jour",
      "ar": "تحديث متاح: {1}  ·  القائمة > التحديثات"}, ("list",)),
    (r"Fork (.+)…", {"*": "Fork {1}…"}, ()),
    (r"Convirtiendo (.+) \(solo la primera vez\)\.\.\.", {"en": "Converting {1} (first run only)...",
                                                          "zh": "正在转换 {1}（仅首次）...", "hi": "{1} परिवर्तित हो रहा है (केवल पहली बार)...",
                                                          "fr": "Conversion de {1} (première fois seulement)...",
                                                          "ar": "جارٍ تحويل {1} (المرة الأولى فقط)..."}, ()),
    (r"Ejecutando (.+)\.\.\.", {"en": "Running {1}...", "zh": "正在运行 {1}...", "hi": "{1} चल रहा है...",
                                "fr": "Exécution de {1}...", "ar": "جارٍ تشغيل {1}..."}, ()),
    (r"Proceso terminado con codigo (.+)\.", {"en": "Process exited with code {1}.", "zh": "进程已退出，代码 {1}。",
                                              "hi": "प्रोसेस कोड {1} के साथ बंद हुई।", "fr": "Processus terminé avec le code {1}.",
                                              "ar": "انتهت العملية بالرمز {1}."}, ()),
    (r"Modulos adicionales: (.+)", {"en": "Extra modules: {1}", "zh": "额外模块：{1}", "hi": "अतिरिक्त मॉड्यूल: {1}",
                                    "fr": "Modules supplémentaires : {1}", "ar": "وحدات إضافية: {1}"}, ()),
    (r"Extrayendo ELF de (.+)\.\.\.", {"en": "Extracting ELF from {1}...", "zh": "正在从 {1} 提取 ELF...",
                                       "hi": "{1} से ELF निकाला जा रहा है...", "fr": "Extraction de l'ELF de {1}...",
                                       "ar": "جارٍ استخراج ELF من {1}..."}, ()),
    (r"Aviso: (.+)", {"en": "Warning: {1}", "zh": "警告：{1}", "hi": "चेतावनी: {1}", "fr": "Avertissement : {1}",
                      "ar": "تحذير: {1}"}, ()),
    (r"El relinker fallo \(codigo (.+)\)\. Revisa el registro\.",
     {"en": "The relinker failed (code {1}). Check the log.", "zh": "relinker 失败（代码 {1}）。请查看日志。",
      "hi": "relinker विफल (कोड {1})। लॉग देखें।", "fr": "Le relinker a échoué (code {1}). Consultez le journal.",
      "ar": "فشل relinker (الرمز {1}). راجع السجل."}, ()),
    (r"(\d+) commits nuevos\. Fusionando\.\.\.", {"en": "{1} new commits. Merging...", "zh": "{1} 个新提交。正在合并...",
                                                  "hi": "{1} नए कमिट। मर्ज हो रहा है...", "fr": "{1} nouveaux commits. Fusion...",
                                                  "ar": "{1} التزامات جديدة. جارٍ الدمج..."}, ()),
    (r"Clonando (.+)\.\.\.", {"en": "Cloning {1}...", "zh": "正在克隆 {1}...", "hi": "{1} क्लोन हो रहा है...",
                              "fr": "Clonage de {1}...", "ar": "جارٍ استنساخ {1}..."}, ()),
    (r"Fork al dia: (.+)", {"en": "Fork up to date: {1}", "zh": "Fork 已是最新：{1}", "hi": "Fork अद्यतन: {1}",
                            "fr": "Fork à jour : {1}", "ar": "Fork محدّث: {1}"}, ()),
    (r"Versión estable (.+) instalada\.", {"en": "Stable version {1} installed.", "zh": "已安装稳定版 {1}。",
                                           "hi": "स्थिर संस्करण {1} स्थापित हुआ।", "fr": "Version stable {1} installée.",
                                           "ar": "تم تثبيت النسخة المستقرة {1}."}, ()),
    (r"Saves importados de (.+)", {"en": "Saves imported from {1}", "zh": "已从 {1} 导入存档", "hi": "{1} से सेव आयात किए गए",
                                   "fr": "Sauvegardes importées depuis {1}", "ar": "تم استيراد الحفظ من {1}"}, ()),
    (r"Auditoría de funciones falló: (.+)", {"en": "Function check failed: {1}", "zh": "函数检查失败：{1}",
                                             "hi": "फ़ंक्शन जाँच विफल: {1}", "fr": "Échec de la vérification des fonctions : {1}",
                                             "ar": "فشل فحص الدوال: {1}"}, ()),
]

_EXACT = {}
for row in T:
    _EXACT[row[0]] = dict(zip(LANG_ORDER, row[1:]))
_PATTERNS = [(re.compile("^" + p + "$", re.S), tpl, groups) for p, tpl, groups in PATTERNS]
SEPARATORS = ("   ·   ", "  ·  ")
_cache = {}


def tr(s, lang):
    if lang == "es" or not s:
        return s
    key = (s, lang)
    if key in _cache:
        return _cache[key]
    out = None
    row = _EXACT.get(s)
    if row:
        out = row.get(lang)
    if out is None:
        for p, tpl, groups in _PATTERNS:
            m = p.match(s)
            if not m:
                continue
            template = tpl.get(lang) or tpl.get("*") or tpl.get("en")
            values = {}
            for i in range(1, (p.groups or 0) + 1):
                v = m.group(i) or ""
                if i in groups:
                    v = tr(v, lang)
                elif "list" in groups:
                    v = (" / ").join(tr(x.strip().capitalize(), lang) for x in v.split(" y "))
                values[str(i)] = v
            out = re.sub(r"\{(\d)\}", lambda mm: values.get(mm.group(1), ""), template)
            break
    if out is None:
        for sep in SEPARATORS:
            if sep in s:
                out = sep.join(tr(part, lang) for part in s.split(sep))
                break
    if out is None:
        out = s
    if len(_cache) < 8000:
        _cache[key] = out
    return out
