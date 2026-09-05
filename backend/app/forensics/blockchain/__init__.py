from app.forensics.blockchain.provider import BlockchainProvider, AnchorResult, VerificationResult
from app.forensics.blockchain.fabric_provider import HyperledgerFabricProvider
from app.forensics.blockchain.mock_provider import MockBlockchainProvider

_global_provider: BlockchainProvider = None

def get_blockchain_provider() -> BlockchainProvider:
    global _global_provider
    if _global_provider is None:
        _global_provider = HyperledgerFabricProvider()
    return _global_provider

def set_blockchain_provider(provider: BlockchainProvider) -> None:
    global _global_provider
    _global_provider = provider
