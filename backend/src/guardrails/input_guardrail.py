import re

FARM_WORDS = re.compile(r'\b(organic|farm\w*|agricultur\w*|crop\w*|cultivat\w*|soil|compost\w*|vermicompost\w*|'
    r'fertiliz\w*|fertilis\w*|pesticid\w*|insecticid\w*|pest\w*|disease\w*|irrigat\w*|seed\w*|'
    r'plant\w*|harvest\w*|ginger|cardamom|tomato\w*|vegetable\w*|fruit\w*|manure|rotation|'
    r'apeda|pgs|horticultur\w*|icar|certification|aphid\w*|cabbage|maize|rice|millet|potato\w*|'
    r'prun\w*|water\w*|weed\w*|seedling\w*|graft\w*|nurser\w*|apple\w*|orange\w*|'
    r'mandarin|pear\w*|orchard\w*|nutrient\w*|turmeric|radish|pea\w*|bean\w*|buckwheat)\b', re.I)
UNRELATED = re.compile(r'\b(code|python|javascript|celebrity|movie|film|cricket|bitcoin|president|prime minister)\b', re.I)
FOLLOWUP = re.compile(r'^(and |what about |how (much|often|long)|when |can (i|we|you) |which |is (it|that) |tell me more|why |what dosage)', re.I)


def in_scope(question, history):
    native_farming = re.compile(r'खेती|कृषि|बाली|अदुवा|अलैँची|जैविक|कम्पोस्ट|माटो|मलखाद|kheti|aduwa|biruwa', re.I)
    if UNRELATED.search(question):
        return False
    if FARM_WORDS.search(question) or native_farming.search(question):
        return True
    return bool(FOLLOWUP.search(question.strip()) and any(FARM_WORDS.search(item['content']) or native_farming.search(item['content'])
                for item in history if item['role'] == 'user'))


def local_message(kind, language):
    messages = {
        'refusal': {
            'en': 'I am Krishi Mitra, and I specialize in organic farming information for Sikkim. Please ask me a question related to organic farming, crops, or agricultural practices.',
            'ne': 'म कृषि मित्र हुँ। म सिक्किमको जैविक खेतीसम्बन्धी जानकारी दिन्छु। कृपया जैविक खेती, बाली वा कृषि अभ्यासबारे प्रश्न सोध्नुहोस्।',
            'ne-Latn': 'Ma Krishi Mitra hu. Ma Sikkim ko organic kheti sambandhi jankari dinchhu. Kripaya organic kheti, bali wa krishi bare prasna sodhnuhos.',
        },
        'insufficient': {
            'en': 'I do not have sufficient verified source material to answer this reliably. Please add a relevant agricultural document to the Knowledge Base.',
            'ne': 'यस प्रश्नको भरपर्दो उत्तर दिन पर्याप्त प्रमाणित स्रोत उपलब्ध छैन। कृपया ज्ञान भण्डारमा सम्बन्धित कृषि दस्तावेज थप्नुहोस्।',
            'ne-Latn': 'Yo prasna ko bharpardo uttar dina paryapta pramanit srot chhaina. Kripaya Knowledge Base ma sambandhit krishi document thapnuhos.',
        },
    }
    return messages[kind].get(language, messages[kind]['en'])
