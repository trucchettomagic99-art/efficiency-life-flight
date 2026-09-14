#!/usr/bin/env python3
"""Aggiunge le tre righe della missione di piattaforma, in 36 lingue.

La home diceva cose di Flight: "Scegli l'opzione migliore per te" e un
occhiello coi voli. Ma la home non e' il motore, e' la porta del gruppo, e
Flight e' solo il primo dei cinque moduli. Se la porta parla di voli, Stay,
Rail, Drive ed Energy nascono senza casa e Google impara che questo dominio
parla di aerei — che e' meno di quello che vuole essere.

La missione in una riga: **misurare il rendimento delle cose che compri**.
Quanto ottieni diviso quanto spendi — che e' letteralmente la lettera eta del
marchio, e vale identica per un volo, una notte d'albergo, un treno,
un'auto o un contratto della luce. Da qui le tre chiavi nuove.

Idempotente: se le chiavi ci sono gia', non tocca niente.

    python scripts/aggiungi_missione.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

# La frase e' spezzata in due perche' il titolo va a capo li', con la seconda
# meta' nel colore del marchio: "Quanto ottieni, / diviso quanto spendi."
H1A = {
"it": "Quanto ottieni,", "en": "What you get,", "es": "Lo que obtienes,",
"fr": "Ce que vous obtenez,", "de": "Was du bekommst,", "pt": "O que recebes,",
"nl": "Wat je krijgt,", "sv": "Vad du får,", "da": "Hvad du får,",
"no": "Hva du får,", "fi": "Mitä saat,", "pl": "To, co dostajesz,",
"cs": "Co získáš,", "hu": "Amit kapsz,", "ro": "Ce primești,",
"el": "Αυτό που παίρνεις,", "bg": "Това, което получаваш,", "ru": "Что вы получаете,",
"uk": "Те, що ви отримуєте,", "tr": "Aldığın değer,", "ar": "ما تحصل عليه،",
"fa": "آنچه می‌گیری،", "he": "מה שאתה מקבל,", "ur": "جو آپ کو ملتا ہے،",
"hi": "जो आपको मिलता है,", "bn": "যা আপনি পান,", "ta": "நீங்கள் பெறுவது,",
"th": "สิ่งที่คุณได้", "vi": "Thứ bạn nhận được,", "id": "Apa yang kamu dapat,",
"ms": "Apa yang anda dapat,", "tl": "Ang nakukuha mo,", "sw": "Unachopata,",
"zh": "你得到的，", "ja": "得られるものを、", "ko": "얻는 것을,",
}

H1B = {
"it": "diviso quanto spendi.", "en": "divided by what you spend.",
"es": "dividido por lo que gastas.", "fr": "divisé par ce que vous dépensez.",
"de": "geteilt durch das, was du zahlst.", "pt": "dividido pelo que gastas.",
"nl": "gedeeld door wat je betaalt.", "sv": "delat med vad du betalar.",
"da": "divideret med hvad du betaler.", "no": "delt på hva du betaler.",
"fi": "jaettuna sillä, mitä maksat.", "pl": "podzielone przez to, co płacisz.",
"cs": "děleno tím, co zaplatíš.", "hu": "osztva azzal, amit fizetsz.",
"ro": "împărțit la cât plătești.", "el": "διά αυτό που πληρώνεις.",
"bg": "разделено на това, което плащаш.", "ru": "делённое на то, что платите.",
"uk": "поділене на те, що платите.", "tr": "ödediğine bölünür.",
"ar": "مقسومًا على ما تدفعه.", "fa": "تقسیم بر آنچه می‌پردازی.",
"he": "חלקי מה שאתה משלם.", "ur": "تقسیم اس پر جو آپ خرچ کرتے ہیں۔",
"hi": "बँटा उससे जो आप खर्च करते हैं।", "bn": "ভাগ করুন যা খরচ করেন তা দিয়ে।",
"ta": "நீங்கள் செலவழிப்பதால் வகுக்கப்பட்டது.", "th": "หารด้วยสิ่งที่คุณจ่าย",
"vi": "chia cho thứ bạn bỏ ra.", "id": "dibagi apa yang kamu bayar.",
"ms": "dibahagi dengan apa yang anda bayar.", "tl": "hinati sa binabayaran mo.",
"sw": "kugawanywa na unacholipa.", "zh": "除以你付出的。",
"ja": "支払うもので割る。", "ko": "지불한 것으로 나눈 값.",
}

LEDE = {
"it": "Efficiency Life misura il rendimento di ogni spesa e mette in fila le opzioni per valore reale, non per prezzo. Il primo modulo è Flight: voli diretti ordinati per chilometri per euro. Seguiranno Stay, Rail, Drive ed Energy.",
"en": "Efficiency Life measures the return on what you spend and ranks the options by real value, not by price. The first module is Flight: direct flights ranked by kilometres per euro. Stay, Rail, Drive and Energy follow.",
"es": "Efficiency Life mide el rendimiento de cada gasto y ordena las opciones por valor real, no por precio. El primer módulo es Flight: vuelos directos ordenados por kilómetros por euro. Seguirán Stay, Rail, Drive y Energy.",
"fr": "Efficiency Life mesure le rendement de chaque dépense et classe les options par valeur réelle, pas par prix. Le premier module est Flight : vols directs classés au kilomètre par euro. Suivront Stay, Rail, Drive et Energy.",
"de": "Efficiency Life misst den Ertrag jeder Ausgabe und ordnet die Optionen nach echtem Wert statt nach Preis. Das erste Modul ist Flight: Direktflüge nach Kilometern pro Euro. Es folgen Stay, Rail, Drive und Energy.",
"pt": "A Efficiency Life mede o rendimento de cada despesa e ordena as opções por valor real, não por preço. O primeiro módulo é o Flight: voos diretos ordenados por quilómetros por euro. Seguem-se Stay, Rail, Drive e Energy.",
"nl": "Efficiency Life meet het rendement van elke uitgave en rangschikt de opties op echte waarde, niet op prijs. De eerste module is Flight: directe vluchten op kilometers per euro. Stay, Rail, Drive en Energy volgen.",
"sv": "Efficiency Life mäter avkastningen på varje utgift och rangordnar alternativen efter verkligt värde, inte pris. Första modulen är Flight: direktflyg sorterade efter kilometer per euro. Stay, Rail, Drive och Energy följer.",
"da": "Efficiency Life måler udbyttet af hver udgift og rangordner mulighederne efter reel værdi, ikke pris. Første modul er Flight: direkte fly sorteret efter kilometer pr. euro. Stay, Rail, Drive og Energy følger.",
"no": "Efficiency Life måler avkastningen på hver utgift og rangerer alternativene etter reell verdi, ikke pris. Første modul er Flight: direktefly sortert etter kilometer per euro. Stay, Rail, Drive og Energy følger.",
"fi": "Efficiency Life mittaa jokaisen euron tuoton ja järjestää vaihtoehdot todellisen arvon mukaan, ei hinnan. Ensimmäinen moduuli on Flight: suorat lennot kilometreinä euroa kohti. Seuraavat ovat Stay, Rail, Drive ja Energy.",
"pl": "Efficiency Life mierzy zwrot z każdego wydatku i porządkuje opcje według realnej wartości, nie ceny. Pierwszy moduł to Flight: loty bezpośrednie według kilometrów na euro. Dalej Stay, Rail, Drive i Energy.",
"cs": "Efficiency Life měří výnos každého výdaje a řadí možnosti podle skutečné hodnoty, ne podle ceny. První modul je Flight: přímé lety podle kilometrů na euro. Následují Stay, Rail, Drive a Energy.",
"hu": "Az Efficiency Life megméri, mit hoz vissza minden kiadás, és valódi érték szerint rangsorol, nem ár szerint. Az első modul a Flight: közvetlen járatok kilométer/euró alapon. Jön a Stay, Rail, Drive és Energy.",
"ro": "Efficiency Life măsoară randamentul fiecărei cheltuieli și ordonează opțiunile după valoare reală, nu după preț. Primul modul este Flight: zboruri directe după kilometri pe euro. Urmează Stay, Rail, Drive și Energy.",
"el": "Το Efficiency Life μετρά την απόδοση κάθε δαπάνης και κατατάσσει τις επιλογές με βάση την πραγματική αξία, όχι την τιμή. Πρώτη ενότητα το Flight: απευθείας πτήσεις ανά χιλιόμετρο το ευρώ. Ακολουθούν Stay, Rail, Drive και Energy.",
"bg": "Efficiency Life измерва възвръщаемостта на всеки разход и подрежда вариантите по реална стойност, не по цена. Първият модул е Flight: директни полети по километри на евро. Следват Stay, Rail, Drive и Energy.",
"ru": "Efficiency Life измеряет отдачу от каждой траты и выстраивает варианты по реальной ценности, а не по цене. Первый модуль — Flight: прямые рейсы по километрам на евро. Далее Stay, Rail, Drive и Energy.",
"uk": "Efficiency Life вимірює віддачу від кожної витрати й упорядковує варіанти за реальною цінністю, а не за ціною. Перший модуль — Flight: прямі рейси за кілометрами на євро. Далі Stay, Rail, Drive та Energy.",
"tr": "Efficiency Life her harcamanın getirisini ölçer ve seçenekleri fiyata değil gerçek değere göre sıralar. İlk modül Flight: euro başına kilometreye göre sıralanan direkt uçuşlar. Ardından Stay, Rail, Drive ve Energy.",
"ar": "يقيس Efficiency Life العائد من كل إنفاق ويرتّب الخيارات حسب القيمة الحقيقية لا حسب السعر. الوحدة الأولى هي Flight: رحلات مباشرة مرتّبة بالكيلومتر لكل يورو. تليها Stay وRail وDrive وEnergy.",
"fa": "Efficiency Life بازده هر هزینه را می‌سنجد و گزینه‌ها را بر پایهٔ ارزش واقعی مرتب می‌کند، نه قیمت. نخستین بخش Flight است: پروازهای مستقیم بر پایهٔ کیلومتر به ازای هر یورو. سپس Stay، Rail، Drive و Energy.",
"he": "Efficiency Life מודדת את התשואה של כל הוצאה ומדרגת את האפשרויות לפי ערך אמיתי, לא לפי מחיר. המודול הראשון הוא Flight: טיסות ישירות לפי קילומטרים לאירו. אחריו Stay, Rail, Drive ו-Energy.",
"ur": "Efficiency Life ہر خرچ کا حاصل ناپتا ہے اور اختیارات کو قیمت کے بجائے اصل قدر کے مطابق ترتیب دیتا ہے۔ پہلا ماڈیول Flight ہے: فی یورو کلومیٹر کے حساب سے براہِ راست پروازیں۔ پھر Stay، Rail، Drive اور Energy۔",
"hi": "Efficiency Life हर खर्च का प्रतिफल मापता है और विकल्पों को कीमत से नहीं, असली मूल्य से क्रम में रखता है। पहला मॉड्यूल Flight है: प्रति यूरो किलोमीटर के हिसाब से सीधी उड़ानें। आगे Stay, Rail, Drive और Energy।",
"bn": "Efficiency Life প্রতিটি খরচের প্রতিদান মাপে এবং দাম নয়, প্রকৃত মূল্য অনুযায়ী বিকল্প সাজায়। প্রথম মডিউল Flight: প্রতি ইউরোতে কিলোমিটার হিসেবে সরাসরি ফ্লাইট। এরপর Stay, Rail, Drive ও Energy।",
"ta": "Efficiency Life ஒவ்வொரு செலவின் பலனையும் அளந்து, விலையால் அல்லாமல் உண்மையான மதிப்பால் விருப்பங்களை வரிசைப்படுத்துகிறது. முதல் பகுதி Flight: ஒரு யூரோவுக்கு கிலோமீட்டர் அடிப்படையில் நேரடி விமானங்கள். அடுத்து Stay, Rail, Drive, Energy.",
"th": "Efficiency Life วัดผลตอบแทนของทุกการใช้จ่าย และจัดอันดับตัวเลือกตามมูลค่าจริง ไม่ใช่ตามราคา โมดูลแรกคือ Flight: เที่ยวบินตรงเรียงตามกิโลเมตรต่อยูโร ตามด้วย Stay, Rail, Drive และ Energy",
"vi": "Efficiency Life đo hiệu quả của mỗi khoản chi và xếp hạng lựa chọn theo giá trị thực, không theo giá. Mô-đun đầu tiên là Flight: chuyến bay thẳng xếp theo ki-lô-mét trên mỗi euro. Tiếp theo là Stay, Rail, Drive và Energy.",
"id": "Efficiency Life mengukur hasil dari setiap pengeluaran dan mengurutkan pilihan berdasarkan nilai nyata, bukan harga. Modul pertama adalah Flight: penerbangan langsung menurut kilometer per euro. Menyusul Stay, Rail, Drive, dan Energy.",
"ms": "Efficiency Life mengukur pulangan setiap perbelanjaan dan menyusun pilihan mengikut nilai sebenar, bukan harga. Modul pertama ialah Flight: penerbangan terus mengikut kilometer per euro. Menyusul Stay, Rail, Drive dan Energy.",
"tl": "Sinusukat ng Efficiency Life ang pakinabang ng bawat gastos at inaayos ang mga pagpipilian ayon sa tunay na halaga, hindi presyo. Ang unang module ay Flight: direktang lipad ayon sa kilometro kada euro. Susunod ang Stay, Rail, Drive at Energy.",
"sw": "Efficiency Life hupima mavuno ya kila matumizi na kupanga chaguo kwa thamani halisi, si bei. Moduli ya kwanza ni Flight: safari za moja kwa moja kwa kilomita kwa euro. Zitafuata Stay, Rail, Drive na Energy.",
"zh": "Efficiency Life 衡量每一笔支出的回报，按真实价值而不是价格排序。第一个模块是 Flight：按每欧元公里数排列的直飞航班。随后是 Stay、Rail、Drive 和 Energy。",
"ja": "Efficiency Life は支出あたりの成果を測り、価格ではなく実質的な価値で選択肢を並べます。最初のモジュールは Flight — 1ユーロあたりの距離で並ぶ直行便です。Stay、Rail、Drive、Energy が続きます。",
"ko": "Efficiency Life는 지출 대비 성과를 재고, 가격이 아니라 실질 가치로 선택지를 줄 세웁니다. 첫 모듈은 Flight — 유로당 킬로미터로 정렬한 직항편입니다. 이어서 Stay, Rail, Drive, Energy.",
}

NUOVE = {'plat_h1a': H1A, 'plat_h1b': H1B, 'plat_lede': LEDE}


def main() -> int:
    p = pathlib.Path('src/i18n.js')
    s = p.read_text(encoding='utf-8')
    m = re.search(r'const KEYS = \[(.*?)\];', s, re.S)
    keys = json.loads('[' + m.group(1) + ']')

    da_aggiungere = [k for k in NUOVE if k not in keys]
    if not da_aggiungere:
        print('le chiavi ci sono gia\': niente da fare')
        return 0

    righe = re.findall(r'^([a-z][a-zA-Z-]*):(\[.*?\]),?$', s, re.M)
    mancanti = [c for c, _ in righe for k in da_aggiungere if c not in NUOVE[k]]
    if mancanti:
        print('traduzioni mancanti per:', sorted(set(mancanti)))
        return 1

    nuove_keys = keys + da_aggiungere
    s = s.replace(m.group(0),
                  'const KEYS = [' + ','.join(json.dumps(k) for k in nuove_keys) + '];', 1)

    for code, arr in righe:
        v = json.loads(arr)
        if len(v) != len(keys):
            print('riga disallineata:', code)
            return 1
        v += [NUOVE[k][code] for k in da_aggiungere]
        s = s.replace(code + ':' + arr + ',', code + ':' + json.dumps(v, ensure_ascii=False) + ',', 1)

    p.write_text(s, encoding='utf-8')

    # rilettura di controllo
    s2 = p.read_text(encoding='utf-8')
    k2 = json.loads('[' + re.search(r'const KEYS = \[(.*?)\];', s2, re.S).group(1) + ']')
    for code, arr in re.findall(r'^([a-z][a-zA-Z-]*):(\[.*?\]),?$', s2, re.M):
        v = json.loads(arr)
        assert len(v) == len(k2), f'{code}: {len(v)} valori su {len(k2)} chiavi'
        for k in da_aggiungere:
            assert v[k2.index(k)].strip(), f'{code}: {k} vuoto'
    print(f"aggiunte {da_aggiungere} a {len(righe)} lingue; righe allineate")
    return 0


if __name__ == '__main__':
    sys.exit(main())
