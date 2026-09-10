#!/usr/bin/env python3
"""Riscrive l'occhiello e il suggerimento del filtro "Quando" in 36 lingue.

I pulsanti parlano in mesi (30 giorni, 1-2 M, ... 6+ M) dal 9 settembre, ma
l'etichetta sopra diceva ancora "Giorni alla partenza": corretto alla lettera,
perche' il filtro conta giorni, ma stonava. Italiano e inglese erano gia' stati
aggiornati a mano; le altre trentaquattro lingue no, e il sito diceva "Tage bis
zum Abflug" sopra pulsanti che dicono "1-2 Mon".

Le tabelle di src/i18n.js sono array posizionali: si legge, si verifica la
lunghezza, si sostituisce alla posizione giusta e si riscrive con JSON, che si
occupa da solo di virgolette e apostrofi.
"""
import json
import pathlib
import re
import sys

# f_window: l'occhiello accanto a "Quando"
FINESTRA = {
"en": "Departure window", "it": "Periodo di partenza", "es": "Periodo de salida",
"fr": "Période de départ", "de": "Reisezeitraum", "pt": "Período de partida",
"nl": "Vertrekperiode", "sv": "Avreseperiod", "da": "Afrejseperiode",
"no": "Avreiseperiode", "fi": "Lähtöajankohta", "pl": "Okres wylotu",
"cs": "Období odletu", "hu": "Indulási időszak", "ro": "Perioada de plecare",
"el": "Περίοδος αναχώρησης", "bg": "Период на заминаване", "ru": "Период вылета",
"uk": "Період вильоту", "tr": "Kalkış dönemi", "ar": "فترة المغادرة",
"fa": "بازه پرواز", "he": "תקופת היציאה", "ur": "روانگی کا دورانیہ",
"hi": "प्रस्थान अवधि", "bn": "যাত্রার সময়কাল", "ta": "புறப்படும் காலம்",
"th": "ช่วงเวลาเดินทาง", "vi": "Khoảng thời gian khởi hành",
"id": "Periode keberangkatan", "ms": "Tempoh berlepas", "tl": "Panahon ng pag-alis",
"sw": "Kipindi cha kuondoka", "zh": "出发时段", "ja": "出発時期", "ko": "출발 시기",
}

# f_window_h: la riga di spiegazione sotto
SPIEGA = {
"en": "When you plan to leave, counted from today. You can pick more than one.",
"it": "Quando intendi partire, contato da oggi. Puoi scegliere piu' intervalli.",
"es": "Cuándo piensas salir, contado desde hoy. Puedes elegir varios.",
"fr": "Quand vous comptez partir, à compter d'aujourd'hui. Plusieurs choix possibles.",
"de": "Wann Sie abreisen wollen, ab heute gerechnet. Mehrfachauswahl möglich.",
"pt": "Quando pretende partir, a contar de hoje. Pode escolher vários.",
"nl": "Wanneer je wilt vertrekken, geteld vanaf vandaag. Meerdere mogelijk.",
"sv": "När du vill resa, räknat från i dag. Du kan välja flera.",
"da": "Hvornår du vil rejse, regnet fra i dag. Du kan vælge flere.",
"no": "Når du vil reise, regnet fra i dag. Du kan velge flere.",
"fi": "Milloin aiot lähteä, tästä päivästä laskien. Voit valita useita.",
"pl": "Kiedy chcesz wylecieć, licząc od dziś. Możesz wybrać kilka.",
"cs": "Kdy chcete odletět, počítáno ode dneška. Můžete vybrat víc.",
"hu": "Mikor indulnál, a mai naptól számítva. Többet is választhatsz.",
"ro": "Când vrei să pleci, socotit de azi. Poți alege mai multe.",
"el": "Πότε σκοπεύετε να φύγετε, από σήμερα. Μπορείτε να επιλέξετε πολλά.",
"bg": "Кога смятате да тръгнете, смятано от днес. Може да изберете няколко.",
"ru": "Когда вы собираетесь вылететь, считая от сегодня. Можно выбрать несколько.",
"uk": "Коли ви плануєте вилетіти, рахуючи від сьогодні. Можна обрати кілька.",
"tr": "Ne zaman yola çıkmak istediğiniz, bugünden itibaren. Birden fazla seçebilirsiniz.",
"ar": "متى تنوي السفر، اعتبارًا من اليوم. يمكنك اختيار أكثر من فترة.",
"fa": "چه زمانی قصد سفر دارید، از امروز. می‌توانید چند بازه را انتخاب کنید.",
"he": "מתי בכוונתך לצאת, מהיום. אפשר לבחור כמה תקופות.",
"ur": "آپ کب روانہ ہونا چاہتے ہیں، آج سے شمار۔ ایک سے زیادہ چن سکتے ہیں۔",
"hi": "आप कब निकलना चाहते हैं, आज से गिनकर। एक से ज़्यादा चुन सकते हैं।",
"bn": "আপনি কখন রওনা দিতে চান, আজ থেকে গণনা। একাধিক বেছে নিতে পারেন।",
"ta": "நீங்கள் எப்போது புறப்பட விரும்புகிறீர்கள், இன்றிலிருந்து. பலவற்றைத் தேர்வு செய்யலாம்.",
"th": "คุณตั้งใจจะเดินทางเมื่อไร นับจากวันนี้ เลือกได้มากกว่าหนึ่งช่วง",
"vi": "Bạn định khởi hành khi nào, tính từ hôm nay. Có thể chọn nhiều khoảng.",
"id": "Kapan Anda berangkat, dihitung dari hari ini. Bisa pilih lebih dari satu.",
"ms": "Bila anda mahu berlepas, dikira dari hari ini. Boleh pilih lebih daripada satu.",
"tl": "Kailan mo balak umalis, bilang mula ngayon. Puwedeng pumili ng higit sa isa.",
"sw": "Unapopanga kusafiri, kuanzia leo. Unaweza kuchagua zaidi ya kimoja.",
"zh": "你打算什么时候出发，从今天算起。可以多选。",
"ja": "いつ出発するか、今日から数えて。複数選べます。",
"ko": "언제 떠날지, 오늘부터 계산합니다. 여러 개 고를 수 있습니다.",
}


def main() -> int:
    p = pathlib.Path('src/i18n.js')
    s = p.read_text(encoding='utf-8')
    m = re.search(r'const KEYS = \[(.*?)\];', s, re.S)
    keys = json.loads('[' + m.group(1) + ']')
    i_win, i_hint = keys.index('f_window'), keys.index('f_window_h')

    righe = re.findall(r'^([a-z][a-zA-Z-]*):(\[.*?\]),?$', s, re.M)
    mancanti = [c for c, _ in righe if c not in FINESTRA or c not in SPIEGA]
    if mancanti:
        print('traduzioni mancanti per:', mancanti)
        return 1

    cambiate = 0
    for code, arr in righe:
        v = json.loads(arr)
        if len(v) != len(keys):
            print('riga disallineata:', code)
            return 1
        if v[i_win] == FINESTRA[code] and v[i_hint] == SPIEGA[code]:
            continue
        v[i_win], v[i_hint] = FINESTRA[code], SPIEGA[code]
        s = s.replace(code + ':' + arr + ',', code + ':' + json.dumps(v, ensure_ascii=False) + ',', 1)
        cambiate += 1

    p.write_text(s, encoding='utf-8')

    # rilettura di controllo: nessuna riga deve essersi rotta
    s2 = p.read_text(encoding='utf-8')
    k2 = json.loads('[' + re.search(r'const KEYS = \[(.*?)\];', s2, re.S).group(1) + ']')
    for code, arr in re.findall(r'^([a-z][a-zA-Z-]*):(\[.*?\]),?$', s2, re.M):
        v = json.loads(arr)
        assert len(v) == len(k2), f'{code}: {len(v)} valori su {len(k2)} chiavi'
        assert v[i_win].strip() and v[i_hint].strip(), f'{code}: valore vuoto'
    print(f'aggiornate {cambiate} lingue su {len(righe)}; tutte le righe restano allineate')
    return 0


if __name__ == '__main__':
    sys.exit(main())
