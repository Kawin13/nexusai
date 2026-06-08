"""
NexusAI — Text utilities
Handles: preprocessing, synonym/abbreviation expansion, document assembly.
No external model required — pure Python + NLTK (with regex fallback).
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── NLTK bootstrap (downloads ~2 MB of data on first run) ─────────
_NLTK_OK = False
try:
    import nltk
    for _pkg in ["punkt", "punkt_tab", "stopwords", "wordnet"]:
        try:
            nltk.download(_pkg, quiet=True)
        except Exception:
            pass
    from nltk.corpus import stopwords as _sw
    from nltk.stem import WordNetLemmatizer
    from nltk.tokenize import word_tokenize as _nltk_tokenize

    _lemmatizer = WordNetLemmatizer()
    _stop_words = set(_sw.words("english")) - {
        "not", "no", "nor", "neither", "never", "without", "vs", "how", "what",
        "why", "when", "where", "which", "who", "is", "are", "do", "does",
    }

    def _tokenize(text: str) -> list[str]:
        return _nltk_tokenize(text)

    def _lemmatize(token: str) -> str:
        return _lemmatizer.lemmatize(token)

    _NLTK_OK = True
    logger.info("NLTK loaded (lemmatizer + stopwords active)")

except Exception as exc:
    # Graceful fallback — simple regex tokeniser, no lemmatisation
    logger.warning(f"NLTK unavailable ({exc}), using simple regex tokeniser")
    _stop_words = {
        "a","an","the","and","or","but","in","on","at","to","for","of","with",
        "by","from","up","about","into","through","during","is","are","was",
        "were","be","been","being","have","has","had","do","does","did","will",
        "would","could","should","may","might","shall","can","need","dare",
        "this","that","these","those","it","its","i","me","my","we","our",
        "you","your","he","she","him","her","they","them","their",
    }

    def _tokenize(text: str) -> list[str]:  # type: ignore[misc]
        return re.findall(r"[a-z0-9]+", text)

    def _lemmatize(token: str) -> str:  # type: ignore[misc]
        # Naive suffix stripping (good enough when NLTK is absent)
        for sfx, rep in [("ing",""), ("tion","te"), ("ness",""), ("ies","y"), ("es",""), ("s","")]:
            if token.endswith(sfx) and len(token) - len(sfx) >= 3:
                return token[: len(token) - len(sfx)] + rep
        return token


# ── Synonym / abbreviation expansion map ──────────────────────────
SYNONYM_MAP: dict[str, list[str]] = {
    # Greetings
    "hi":      ["hello", "greetings"],
    "hey":     ["hello"],
    "bye":     ["goodbye", "farewell"],
    "thanks":  ["thank you"],
    "thx":     ["thank you", "thanks"],
    # Core tech abbreviations
    "ai":      ["artificial intelligence", "machine intelligence"],
    "ml":      ["machine learning", "statistical learning"],
    "dl":      ["deep learning", "neural networks"],
    "nlp":     ["natural language processing", "text processing"],
    "api":     ["application programming interface", "web service", "endpoint", "rest"],
    "db":      ["database", "data store", "sql"],
    "k8s":     ["kubernetes", "container orchestration"],
    "ci/cd":   ["continuous integration", "continuous deployment", "pipeline", "devops"],
    "cicd":    ["continuous integration", "continuous deployment", "pipeline"],
    "iac":     ["infrastructure as code", "terraform", "cloudformation"],
    "orm":     ["object relational mapping", "sqlalchemy", "django orm"],
    "vm":      ["virtual machine", "virtualization"],
    "os":      ["operating system", "linux", "windows"],
    "git":     ["version control", "source control"],
    "sre":     ["site reliability engineering", "reliability"],
    "devops":  ["development operations", "continuous integration", "automation"],
    "llm":     ["large language model", "gpt", "language model", "transformer"],
    "rag":     ["retrieval augmented generation", "retrieval augmentation"],
    "ssl":     ["tls", "https", "encryption", "certificate"],
    "tls":     ["ssl", "https", "encryption"],
    "cdn":     ["content delivery network", "edge network"],
    "sql":     ["structured query language", "relational database", "query"],
    "nosql":   ["non-relational", "mongodb", "cassandra", "document database"],
    "oop":     ["object oriented programming", "classes", "objects", "inheritance"],
    "tdd":     ["test driven development", "unit testing", "testing"],
    "bdd":     ["behavior driven development", "gherkin", "testing"],
    "aws":     ["amazon web services", "cloud", "ec2", "s3"],
    "gcp":     ["google cloud platform", "cloud"],
    "azure":   ["microsoft azure", "cloud"],
    "saas":    ["software as a service", "cloud software"],
    "paas":    ["platform as a service", "cloud platform"],
    "iaas":    ["infrastructure as a service", "cloud infrastructure"],
    "cnn":     ["convolutional neural network", "image recognition", "deep learning"],
    "rnn":     ["recurrent neural network", "sequence model", "lstm"],
    "lstm":    ["long short-term memory", "recurrent neural network", "sequence model"],
    "gan":     ["generative adversarial network", "generative model"],
    "bert":    ["bidirectional encoder representations", "transformer", "nlp model"],
    "gpt":     ["generative pre-trained transformer", "language model", "llm"],
    "http":    ["hypertext transfer protocol", "web protocol", "rest"],
    "https":   ["secure http", "ssl", "tls", "encryption"],
    "tcp":     ["transmission control protocol", "networking"],
    "ip":      ["internet protocol", "networking", "address"],
    "dns":     ["domain name system", "networking", "domain"],
    "ssh":     ["secure shell", "remote access", "terminal"],
    "cli":     ["command line interface", "terminal", "shell"],
    "ide":     ["integrated development environment", "editor", "vscode"],
    "pr":      ["pull request", "code review", "merge request"],
    "mr":      ["merge request", "pull request", "code review"],
    "regex":   ["regular expression", "pattern matching"],
    "async":   ["asynchronous", "concurrency", "non-blocking"],
    "sync":    ["synchronous", "blocking"],
    "crud":    ["create read update delete", "database operations"],
    "rest":    ["representational state transfer", "api", "http", "web service"],
    "graphql": ["graph query language", "api", "query"],
    "grpc":    ["google remote procedure call", "rpc", "api"],
    "jwt":     ["json web token", "authentication", "authorization"],
    "oauth":   ["open authorization", "authentication", "token"],
    "sso":     ["single sign on", "authentication"],
    "mfa":     ["multi-factor authentication", "2fa", "security"],
    "2fa":     ["two-factor authentication", "mfa", "security"],
    "vpn":     ["virtual private network", "networking", "security"],
    "ddos":    ["distributed denial of service", "attack", "cybersecurity"],
    "xss":     ["cross-site scripting", "security", "vulnerability"],
    "csrf":    ["cross-site request forgery", "security", "vulnerability"],
}


def expand_synonyms(text: str) -> str:
    """Append synonym/abbreviation expansions to *text*."""
    text_lower = text.lower()
    expansions: list[str] = []
    for abbr, synonyms in SYNONYM_MAP.items():
        pattern = r"\b" + re.escape(abbr) + r"\b"
        if re.search(pattern, text_lower):
            expansions.extend(synonyms)
    if expansions:
        return text + " " + " ".join(expansions)
    return text


def preprocess(text: str) -> str:
    """
    Lowercase → strip non-alpha → tokenise → lemmatise → remove stopwords.
    Returns a single space-joined string ready for TF-IDF.
    Falls back gracefully if NLTK is unavailable.
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-/]", " ", text)
    tokens = _tokenize(text)
    tokens = [
        _lemmatize(t)
        for t in tokens
        if t not in _stop_words and len(t) > 1
    ]
    return " ".join(tokens)


def make_doc(faq: dict) -> str:
    """
    Build a weighted document string for a FAQ entry.
    The question is repeated 3× for higher TF weight; keywords 2×.
    """
    question = faq.get("question", "")
    answer   = faq.get("answer", "")[:500]
    keywords = " ".join(faq.get("keywords", []))
    combined = f"{question} {question} {question} {keywords} {keywords} {answer}"
    expanded = expand_synonyms(combined)
    return preprocess(expanded)
