from enum import Enum


class ServiceType(str, Enum):
    TARGET   = 'target'
    SPLITTER = 'splitter'
    AGENT    = 'agent'

