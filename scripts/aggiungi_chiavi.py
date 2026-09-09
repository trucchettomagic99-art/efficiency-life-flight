#!/usr/bin/env python3
"""Aggiunge al vocabolario le dieci voci nuove chieste dal rifacimento della
navigazione, e riscrive "Metodo" come "Come funziona".

Le tabelle di src/i18n.js sono array posizionali: la riga di ogni lingua deve
avere esattamente tanti elementi quante sono le chiavi, nello stesso ordine.
Toccarle a mano e' il modo piu' rapido per disallinearle — il 4 settembre una
riga si era rotta cosi'. Qui si legge, si verifica la lunghezza, si aggiunge
in coda e si riscrive con JSON, che si occupa da solo di virgolette e
apostrofi (l'apostrofo di "l'aeroporto" aveva gia' rotto la riga italiana).

Lo script e' idempotente: se le chiavi ci sono gia', non fa nulla.
"""
import json
import pathlib
import re
import sys

NUOVE = ["nav_home", "nav_explore", "about_t", "about_b", "svc_t", "svc_b",
         "avail", "w_any", "w_d30", "w_mo"]

# nav_home, nav_explore, about_t, about_b, svc_t, svc_b, avail, w_any, w_d30, w_mo
V = {
"en": ["Home", "Explore", "About Efficiency Life",
  "Efficiency Life measures what you get for what you spend. Flight, its first module, ranks thousands of real fares by kilometres per euro: you set the budget, the engine finds how far it can take you.",
  "Explore our services", "One method, five areas. Flight is live today; the others are on the way.",
  "Available", "Anytime", "30 days", "M"],
"it": ["Home", "Esplora", "Cos'è Efficiency Life",
  "Efficiency Life misura quanto ottieni per quanto spendi. Flight, il suo primo modulo, ordina migliaia di tariffe reali per chilometri per euro: tu fissi il budget, il motore trova fin dove può portarti.",
  "I nostri servizi", "Un metodo, cinque ambiti. Flight è attivo oggi; gli altri sono in lavorazione.",
  "Disponibile", "Sempre", "30 giorni", "M"],
"es": ["Inicio", "Explorar", "Acerca de Efficiency Life",
  "Efficiency Life mide cuánto obtienes por lo que gastas. Flight, su primer módulo, ordena miles de tarifas reales por kilómetros por euro: tú fijas el presupuesto y el motor encuentra hasta dónde puede llevarte.",
  "Explora nuestros servicios", "Un método, cinco ámbitos. Flight ya está activo; los demás están en camino.",
  "Disponible", "Cuando sea", "30 días", "M"],
"fr": ["Accueil", "Explorer", "À propos d'Efficiency Life",
  "Efficiency Life mesure ce que vous obtenez pour ce que vous dépensez. Flight, son premier module, classe des milliers de tarifs réels par kilomètres par euro : vous fixez le budget, le moteur trouve jusqu'où il peut vous emmener.",
  "Explorez nos services", "Une méthode, cinq domaines. Flight est actif aujourd'hui ; les autres arrivent.",
  "Disponible", "N'importe quand", "30 jours", "M"],
"de": ["Start", "Entdecken", "Über Efficiency Life",
  "Efficiency Life misst, was Sie für Ihr Geld bekommen. Flight, das erste Modul, sortiert Tausende echter Flugpreise nach Kilometern pro Euro: Sie setzen das Budget, die Suche findet, wie weit es Sie bringt.",
  "Unsere Dienste entdecken", "Eine Methode, fünf Bereiche. Flight ist heute aktiv, die anderen folgen.",
  "Verfügbar", "Jederzeit", "30 Tage", "Mon"],
"pt": ["Início", "Explorar", "Sobre a Efficiency Life",
  "A Efficiency Life mede quanto você obtém pelo que gasta. O Flight, seu primeiro módulo, ordena milhares de tarifas reais por quilómetros por euro: você define o orçamento e o motor descobre até onde ele leva.",
  "Explore os nossos serviços", "Um método, cinco áreas. O Flight já está ativo; os outros estão a caminho.",
  "Disponível", "Qualquer data", "30 dias", "M"],
"nl": ["Home", "Ontdekken", "Over Efficiency Life",
  "Efficiency Life meet wat je krijgt voor wat je uitgeeft. Flight, de eerste module, rangschikt duizenden echte tarieven op kilometers per euro: jij bepaalt het budget, de motor zoekt hoe ver dat je brengt.",
  "Ontdek onze diensten", "Eén methode, vijf gebieden. Flight is nu actief; de rest volgt.",
  "Beschikbaar", "Altijd", "30 dagen", "mnd"],
"sv": ["Hem", "Utforska", "Om Efficiency Life",
  "Efficiency Life mäter vad du får för det du betalar. Flight, den första modulen, rangordnar tusentals verkliga priser efter kilometer per euro: du sätter budgeten, motorn hittar hur långt den räcker.",
  "Utforska våra tjänster", "En metod, fem områden. Flight är igång i dag; de övriga är på väg.",
  "Tillgänglig", "När som helst", "30 dagar", "mån"],
"da": ["Hjem", "Udforsk", "Om Efficiency Life",
  "Efficiency Life måler, hvad du får for det, du bruger. Flight, det første modul, rangordner tusindvis af rigtige priser efter kilometer pr. euro: du sætter budgettet, og motoren finder, hvor langt det rækker.",
  "Udforsk vores tjenester", "Én metode, fem områder. Flight er aktiv i dag; de andre er på vej.",
  "Tilgængelig", "Når som helst", "30 dage", "mdr"],
"no": ["Hjem", "Utforsk", "Om Efficiency Life",
  "Efficiency Life måler hva du får for det du bruker. Flight, den første modulen, rangerer tusenvis av ekte priser etter kilometer per euro: du setter budsjettet, og motoren finner hvor langt det rekker.",
  "Utforsk tjenestene våre", "Én metode, fem områder. Flight er i drift i dag; de andre kommer.",
  "Tilgjengelig", "Når som helst", "30 dager", "mnd"],
"fi": ["Etusivu", "Tutustu", "Tietoa Efficiency Lifesta",
  "Efficiency Life mittaa, mitä saat sillä mitä maksat. Flight, sen ensimmäinen osa, järjestää tuhansia todellisia hintoja kilometreinä euroa kohden: sinä asetat budjetin, ja haku etsii kuinka pitkälle se riittää.",
  "Tutustu palveluihimme", "Yksi menetelmä, viisi aluetta. Flight on käytössä nyt; muut ovat tulossa.",
  "Saatavilla", "Milloin vain", "30 päivää", "kk"],
"pl": ["Start", "Odkryj", "O Efficiency Life",
  "Efficiency Life mierzy, ile dostajesz za to, co wydajesz. Flight, jego pierwszy moduł, porządkuje tysiące prawdziwych taryf według kilometrów na euro: ty ustalasz budżet, a wyszukiwarka znajduje, jak daleko zabierze.",
  "Poznaj nasze usługi", "Jedna metoda, pięć obszarów. Flight działa już dziś; pozostałe są w drodze.",
  "Dostępne", "Kiedykolwiek", "30 dni", "mies"],
"cs": ["Domů", "Objevit", "O Efficiency Life",
  "Efficiency Life měří, co dostanete za to, co utratíte. Flight, jeho první modul, řadí tisíce skutečných cen podle kilometrů na euro: vy určíte rozpočet a vyhledávání najde, kam až dosáhne.",
  "Objevte naše služby", "Jedna metoda, pět oblastí. Flight funguje už dnes, ostatní se připravují.",
  "Dostupné", "Kdykoli", "30 dní", "měs"],
"hu": ["Kezdőlap", "Felfedezés", "Az Efficiency Life-ról",
  "Az Efficiency Life azt méri, mennyit kapsz azért, amit kifizetsz. A Flight, az első modulja, több ezer valós viteldíjat rendez kilométer per euró szerint: te megadod a keretet, a kereső megtalálja, meddig visz el.",
  "Fedezd fel a szolgáltatásainkat", "Egy módszer, öt terület. A Flight ma már működik, a többi készül.",
  "Elérhető", "Bármikor", "30 nap", "hó"],
"ro": ["Acasă", "Explorează", "Despre Efficiency Life",
  "Efficiency Life măsoară cât primești pentru cât cheltuiești. Flight, primul său modul, ordonează mii de tarife reale după kilometri pe euro: tu stabilești bugetul, iar motorul găsește până unde te duce.",
  "Explorează serviciile noastre", "O metodă, cinci domenii. Flight este activ azi; celelalte sunt pe drum.",
  "Disponibil", "Oricând", "30 de zile", "luni"],
"el": ["Αρχική", "Εξερεύνηση", "Σχετικά με το Efficiency Life",
  "Το Efficiency Life μετρά τι παίρνεις για όσα ξοδεύεις. Το Flight, η πρώτη του ενότητα, κατατάσσει χιλιάδες πραγματικούς ναύλους ανά χιλιόμετρα το ευρώ: εσύ ορίζεις τον προϋπολογισμό και η μηχανή βρίσκει ως πού φτάνει.",
  "Εξερευνήστε τις υπηρεσίες μας", "Μία μέθοδος, πέντε τομείς. Το Flight λειτουργεί σήμερα· τα υπόλοιπα έρχονται.",
  "Διαθέσιμο", "Οποτεδήποτε", "30 ημέρες", "μήν"],
"bg": ["Начало", "Разгледай", "За Efficiency Life",
  "Efficiency Life измерва какво получавате срещу това, което харчите. Flight, първият му модул, подрежда хиляди реални цени по километри за евро: вие задавате бюджета, а търсачката открива докъде стига.",
  "Разгледайте услугите ни", "Един метод, пет области. Flight работи вече днес; останалите предстоят.",
  "Достъпно", "По всяко време", "30 дни", "мес"],
"ru": ["Главная", "Обзор", "Об Efficiency Life",
  "Efficiency Life измеряет, сколько вы получаете за то, что тратите. Flight, его первый модуль, ранжирует тысячи реальных тарифов по километрам на евро: вы задаёте бюджет, а поиск находит, как далеко он вас увезёт.",
  "Наши сервисы", "Один метод, пять областей. Flight работает уже сегодня, остальные готовятся.",
  "Доступно", "Когда угодно", "30 дней", "мес"],
"uk": ["Головна", "Огляд", "Про Efficiency Life",
  "Efficiency Life вимірює, скільки ви отримуєте за те, що витрачаєте. Flight, його перший модуль, упорядковує тисячі справжніх тарифів за кілометрами на євро: ви задаєте бюджет, а пошук знаходить, як далеко він вас довезе.",
  "Наші сервіси", "Один метод, п'ять напрямів. Flight працює вже сьогодні, решта готується.",
  "Доступно", "Будь-коли", "30 днів", "міс"],
"tr": ["Ana sayfa", "Keşfet", "Efficiency Life hakkında",
  "Efficiency Life, harcadığınıza karşılık ne aldığınızı ölçer. İlk modülü Flight, binlerce gerçek ücreti euro başına kilometreye göre sıralar: bütçeyi siz koyarsınız, motor sizi nereye kadar götürebileceğini bulur.",
  "Hizmetlerimizi keşfedin", "Tek yöntem, beş alan. Flight bugün yayında; diğerleri yolda.",
  "Mevcut", "Her zaman", "30 gün", "ay"],
"ar": ["الرئيسية", "استكشاف", "نبذة عن Efficiency Life",
  "يقيس Efficiency Life ما تحصل عليه مقابل ما تنفقه. وحدته الأولى Flight ترتّب آلاف الأسعار الحقيقية حسب الكيلومترات لكل يورو: أنت تحدّد الميزانية، والمحرّك يجد إلى أي مدى تصل بك.",
  "استكشف خدماتنا", "منهج واحد، خمسة مجالات. Flight متاح اليوم، والبقية في الطريق.",
  "متاح", "أي وقت", "30 يومًا", "شهر"],
"fa": ["خانه", "کاوش", "درباره Efficiency Life",
  "Efficiency Life اندازه می‌گیرد در برابر آنچه خرج می‌کنید چه به دست می‌آورید. Flight، نخستین بخش آن، هزاران نرخ واقعی را بر پایه کیلومتر به ازای هر یورو مرتب می‌کند: شما بودجه را تعیین می‌کنید و موتور می‌یابد تا کجا می‌بردتان.",
  "خدمات ما را ببینید", "یک روش، پنج حوزه. Flight امروز فعال است؛ بقیه در راه‌اند.",
  "در دسترس", "هر زمان", "30 روز", "ماه"],
"he": ["דף הבית", "גלה", "אודות Efficiency Life",
  "‏Efficiency Life מודד מה אתם מקבלים תמורת מה שאתם מוציאים. ‏Flight, המודול הראשון שלו, מדרג אלפי מחירים אמיתיים לפי קילומטרים לאירו: אתם קובעים את התקציב, והמנוע מוצא עד לאן הוא מגיע.",
  "גלו את השירותים שלנו", "שיטה אחת, חמישה תחומים. ‏Flight פעיל היום; השאר בדרך.",
  "זמין", "בכל זמן", "30 ימים", "חוד"],
"ur": ["ہوم", "دریافت", "Efficiency Life کے بارے میں",
  "‏Efficiency Life ماپتا ہے کہ آپ خرچ کے بدلے کیا پاتے ہیں۔ اس کا پہلا حصہ Flight ہزاروں حقیقی کرایوں کو فی یورو کلومیٹر کے حساب سے ترتیب دیتا ہے: بجٹ آپ طے کرتے ہیں، انجن ڈھونڈتا ہے کہ وہ آپ کو کہاں تک لے جا سکتا ہے۔",
  "ہماری خدمات دیکھیں", "ایک طریقہ، پانچ شعبے۔ Flight آج دستیاب ہے؛ باقی راستے میں ہیں۔",
  "دستیاب", "کبھی بھی", "30 دن", "ماہ"],
"hi": ["होम", "एक्सप्लोर", "Efficiency Life के बारे में",
  "Efficiency Life मापता है कि आप जो खर्च करते हैं उसके बदले क्या पाते हैं। इसका पहला हिस्सा Flight हज़ारों असली किरायों को प्रति यूरो किलोमीटर के हिसाब से क्रम देता है: बजट आप तय करते हैं, इंजन ढूँढता है कि वह आपको कितनी दूर ले जा सकता है।",
  "हमारी सेवाएँ देखें", "एक तरीका, पाँच क्षेत्र। Flight आज उपलब्ध है; बाकी रास्ते में हैं।",
  "उपलब्ध", "कभी भी", "30 दिन", "माह"],
"bn": ["হোম", "অন্বেষণ", "Efficiency Life সম্পর্কে",
  "Efficiency Life মাপে আপনি যা খরচ করেন তার বিনিময়ে কী পান। এর প্রথম অংশ Flight হাজার হাজার প্রকৃত ভাড়া ইউরো প্রতি কিলোমিটার হিসেবে সাজায়: বাজেট আপনি ঠিক করেন, ইঞ্জিন খুঁজে বার করে সেটি আপনাকে কত দূর নিয়ে যেতে পারে।",
  "আমাদের পরিষেবা দেখুন", "একটি পদ্ধতি, পাঁচটি ক্ষেত্র। Flight আজ চালু; বাকিগুলি আসছে।",
  "উপলব্ধ", "যেকোনো সময়", "30 দিন", "মাস"],
"ta": ["முகப்பு", "ஆராய்", "Efficiency Life பற்றி",
  "நீங்கள் செலவழிப்பதற்கு ஈடாக என்ன பெறுகிறீர்கள் என்பதை Efficiency Life அளக்கிறது. அதன் முதல் பகுதியான Flight ஆயிரக்கணக்கான உண்மையான கட்டணங்களை யூரோவுக்கு கிலோமீட்டர் அடிப்படையில் வரிசைப்படுத்துகிறது: பட்ஜெட்டை நீங்கள் நிர்ணயிக்கிறீர்கள், எவ்வளவு தூரம் செல்லலாம் என்பதை இயந்திரம் கண்டறிகிறது.",
  "எங்கள் சேவைகளைப் பாருங்கள்", "ஒரு முறை, ஐந்து துறைகள். Flight இன்று செயலில் உள்ளது; மற்றவை வரவுள்ளன.",
  "கிடைக்கிறது", "எப்போது வேண்டுமானாலும்", "30 நாட்கள்", "மாதம்"],
"th": ["หน้าแรก", "สำรวจ", "เกี่ยวกับ Efficiency Life",
  "Efficiency Life วัดว่าคุณได้อะไรกลับมาจากเงินที่จ่ายไป Flight ซึ่งเป็นส่วนแรก จัดอันดับค่าโดยสารจริงหลายพันรายการตามกิโลเมตรต่อยูโร คุณกำหนดงบประมาณ แล้วระบบจะหาว่ามันพาคุณไปได้ไกลแค่ไหน",
  "สำรวจบริการของเรา", "หนึ่งวิธี ห้าด้าน Flight เปิดใช้แล้ววันนี้ ส่วนที่เหลือกำลังตามมา",
  "พร้อมใช้งาน", "เมื่อไรก็ได้", "30 วัน", "เดือน"],
"vi": ["Trang chủ", "Khám phá", "Về Efficiency Life",
  "Efficiency Life đo xem bạn nhận được gì cho số tiền bỏ ra. Flight, phần đầu tiên, xếp hạng hàng nghìn mức giá thật theo số ki-lô-mét trên mỗi euro: bạn đặt ngân sách, còn công cụ tìm xem nó đưa bạn đi được bao xa.",
  "Khám phá dịch vụ của chúng tôi", "Một phương pháp, năm lĩnh vực. Flight đã hoạt động hôm nay; những phần khác đang tới.",
  "Có sẵn", "Bất kỳ lúc nào", "30 ngày", "tháng"],
"id": ["Beranda", "Jelajahi", "Tentang Efficiency Life",
  "Efficiency Life mengukur apa yang Anda dapat dari yang Anda keluarkan. Flight, modul pertamanya, mengurutkan ribuan tarif nyata berdasarkan kilometer per euro: Anda menetapkan anggaran, mesin mencari sejauh mana ia membawa Anda.",
  "Jelajahi layanan kami", "Satu metode, lima bidang. Flight sudah aktif hari ini; yang lain menyusul.",
  "Tersedia", "Kapan saja", "30 hari", "bln"],
"ms": ["Utama", "Terokai", "Tentang Efficiency Life",
  "Efficiency Life mengukur apa yang anda dapat berbanding apa yang anda belanjakan. Flight, modul pertamanya, menyusun ribuan tambang sebenar mengikut kilometer per euro: anda menetapkan bajet, enjin mencari sejauh mana ia membawa anda.",
  "Terokai perkhidmatan kami", "Satu kaedah, lima bidang. Flight aktif hari ini; yang lain menyusul.",
  "Tersedia", "Bila-bila masa", "30 hari", "bln"],
"tl": ["Home", "Tuklasin", "Tungkol sa Efficiency Life",
  "Sinusukat ng Efficiency Life kung ano ang nakukuha mo sa halagang ginagastos mo. Ang Flight, ang unang bahagi nito, ay nag-uuri ng libu-libong tunay na pamasahe ayon sa kilometro kada euro: ikaw ang nagtatakda ng badyet, hahanapin ng makina kung gaano kalayo ka nito madadala.",
  "Tuklasin ang aming mga serbisyo", "Isang paraan, limang larangan. Aktibo na ang Flight ngayon; paparating ang iba.",
  "Magagamit", "Kahit kailan", "30 araw", "buwan"],
"sw": ["Mwanzo", "Gundua", "Kuhusu Efficiency Life",
  "Efficiency Life hupima unachopata kwa unachotumia. Flight, sehemu yake ya kwanza, hupanga maelfu ya nauli halisi kwa kilomita kwa kila euro: wewe unaweka bajeti, injini inatafuta itakupeleka mbali kiasi gani.",
  "Gundua huduma zetu", "Njia moja, nyanja tano. Flight inafanya kazi leo; nyingine zinakuja.",
  "Inapatikana", "Wakati wowote", "Siku 30", "miezi"],
"zh": ["首页", "探索", "关于 Efficiency Life",
  "Efficiency Life 衡量你花的钱换来了什么。它的第一个模块 Flight 按每欧元里程数排列数千条真实票价：预算由你定，引擎找出它能带你走多远。",
  "探索我们的服务", "一套方法，五个领域。Flight 今天已上线，其余正在路上。",
  "已上线", "不限时间", "30 天", "个月"],
"ja": ["ホーム", "探索", "Efficiency Life について",
  "Efficiency Life は、払った額に対して何が得られるかを測ります。最初のモジュールである Flight は、数千件の実際の運賃を 1 ユーロあたりの距離で並べ替えます。予算はあなたが決め、どこまで行けるかはエンジンが見つけます。",
  "サービスを見る", "ひとつの方法、五つの分野。Flight は本日稼働中、ほかは準備中です。",
  "提供中", "いつでも", "30 日", "ヶ月"],
"ko": ["홈", "둘러보기", "Efficiency Life 소개",
  "Efficiency Life는 쓴 돈에 비해 무엇을 얻는지를 측정합니다. 첫 모듈인 Flight는 수천 건의 실제 항공권 가격을 유로당 킬로미터로 정렬합니다. 예산은 당신이 정하고, 얼마나 멀리 갈 수 있는지는 엔진이 찾습니다.",
  "서비스 둘러보기", "하나의 방법, 다섯 개 영역. Flight는 오늘 운영 중이고 나머지는 준비 중입니다.",
  "이용 가능", "언제든지", "30일", "개월"],
}

# "Metodo" diventa "Come funziona": stessa chiave, valore nuovo, cosi' la voce
# di navigazione e il titolo della sezione cambiano insieme.
COME_FUNZIONA = {
"en": "How it works", "it": "Come funziona", "es": "Cómo funciona", "fr": "Comment ça marche",
"de": "So funktioniert es", "pt": "Como funciona", "nl": "Hoe het werkt", "sv": "Så fungerar det",
"da": "Sådan virker det", "no": "Slik fungerer det", "fi": "Näin se toimii", "pl": "Jak to działa",
"cs": "Jak to funguje", "hu": "Hogyan működik", "ro": "Cum funcționează", "el": "Πώς λειτουργεί",
"bg": "Как работи", "ru": "Как это работает", "uk": "Як це працює", "tr": "Nasıl çalışır",
"ar": "كيف يعمل", "fa": "چگونه کار می‌کند", "he": "איך זה עובד", "ur": "یہ کیسے کام کرتا ہے",
"hi": "यह कैसे काम करता है", "bn": "এটি কীভাবে কাজ করে", "ta": "இது எப்படி வேலை செய்கிறது",
"th": "วิธีทำงาน", "vi": "Cách hoạt động", "id": "Cara kerjanya", "ms": "Cara ia berfungsi",
"tl": "Paano ito gumagana", "sw": "Jinsi inavyofanya kazi", "zh": "工作原理",
"ja": "仕組み", "ko": "작동 방식",
}


def main() -> int:
    p = pathlib.Path('src/i18n.js')
    s = p.read_text(encoding='utf-8')

    m = re.search(r'const KEYS = \[(.*?)\];', s, re.S)
    keys = json.loads('[' + m.group(1) + ']')
    if NUOVE[0] in keys:
        print('chiavi gia\' presenti: niente da fare')
        return 0

    i_method = keys.index('nav_method')
    righe = re.findall(r'^([a-z][a-zA-Z-]*):(\[.*?\]),?$', s, re.M)
    if len(righe) != 36:
        print('attese 36 lingue, trovate', len(righe)); return 1

    mancanti = [c for c, _ in righe if c not in V or c not in COME_FUNZIONA]
    if mancanti:
        print('traduzioni mancanti per:', mancanti); return 1

    nuove_keys = keys + NUOVE
    testo_keys = json.dumps(nuove_keys, ensure_ascii=False)
    # a capo ogni nove chiavi, come nel file originale
    pezzi = [json.dumps(k, ensure_ascii=False) for k in nuove_keys]
    blocchi = [' ' + ','.join(pezzi[i:i + 9]) for i in range(0, len(pezzi), 9)]
    testo_keys = '[' + ',\n'.join(blocchi).lstrip() + ']'
    s = s[:m.start()] + 'const KEYS = ' + testo_keys + ';' + s[m.end():]

    for code, arr in righe:
        v = json.loads(arr)
        if len(v) != len(keys):
            print('riga disallineata:', code, len(v)); return 1
        v[i_method] = COME_FUNZIONA[code]
        v = v + V[code]
        nuovo = code + ':' + json.dumps(v, ensure_ascii=False) + ','
        s = s.replace(code + ':' + arr + ',', nuovo, 1)

    p.write_text(s, encoding='utf-8')

    # rilettura di controllo
    s2 = p.read_text(encoding='utf-8')
    k2 = json.loads('[' + re.search(r'const KEYS = \[(.*?)\];', s2, re.S).group(1) + ']')
    r2 = re.findall(r'^([a-z][a-zA-Z-]*):(\[.*?\]),?$', s2, re.M)
    assert len(k2) == len(keys) + len(NUOVE), 'chiavi non aggiunte'
    for code, arr in r2:
        v = json.loads(arr)
        assert len(v) == len(k2), f'{code}: {len(v)} valori su {len(k2)} chiavi'
        assert all(isinstance(x, str) and x.strip() for x in v), f'{code}: valore vuoto'
    print(f'fatto: {len(k2)} chiavi x {len(r2)} lingue, tutte piene')
    return 0


if __name__ == '__main__':
    sys.exit(main())
