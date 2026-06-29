from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Article:
    title:      str
    url:        str
    summary:    str
    source:     str
    category:   str
    published:  Optional[datetime] = None
    raw_text:   str = ""
    score:      float = 0.0          # relevance score assigned by classifier
    sentiment:  str = "neutral"      # bullish / bearish / neutral / mixed

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, other):
        return isinstance(other, Article) and self.url == other.url


class BaseCollector(ABC):
    @abstractmethod
    def collect(self) -> List[Article]:
        ...
