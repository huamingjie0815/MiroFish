"""
Knowledge Graph Adapter Unit Tests

Tests the kg_adapter module API signatures and configuration.
Run with: uv run pytest tests/test_kg_adapter.py -v
"""
import pytest
from unittest.mock import Mock, patch
import os


class TestZepCloudAdapterAPI:
    """Test ZepCloudAdapter API calls match Zep Cloud SDK"""

    def test_create_graph_signature(self):
        """Test create_graph accepts graph_id and name"""
        from app.services.kg_adapter import ZepCloudAdapter
        import inspect

        sig = inspect.signature(ZepCloudAdapter.create_graph)
        params = list(sig.parameters.keys())
        assert 'self' in params
        assert 'graph_id' in params
        assert 'name' in params

    def test_add_episode_signature(self):
        """Test add_episode accepts graph_id and text"""
        from app.services.kg_adapter import ZepCloudAdapter
        import inspect

        sig = inspect.signature(ZepCloudAdapter.add_episode)
        params = list(sig.parameters.keys())
        assert 'graph_id' in params
        assert 'text' in params

    def test_add_episodes_batch_signature(self):
        """Test add_episodes_batch accepts graph_id and texts"""
        from app.services.kg_adapter import ZepCloudAdapter
        import inspect

        sig = inspect.signature(ZepCloudAdapter.add_episodes_batch)
        params = list(sig.parameters.keys())
        assert 'graph_id' in params
        assert 'texts' in params

    def test_set_ontology_signature(self):
        """Test set_ontology accepts graph_id and ontology"""
        from app.services.kg_adapter import ZepCloudAdapter
        import inspect

        sig = inspect.signature(ZepCloudAdapter.set_ontology)
        params = list(sig.parameters.keys())
        assert 'graph_id' in params
        assert 'ontology' in params

    def test_search_signature(self):
        """Test search accepts graph_id, query and limit"""
        from app.services.kg_adapter import ZepCloudAdapter
        import inspect

        sig = inspect.signature(ZepCloudAdapter.search)
        params = list(sig.parameters.keys())
        assert 'graph_id' in params
        assert 'query' in params
        assert 'limit' in params

    def test_get_nodes_signature(self):
        """Test get_nodes accepts graph_id, limit and cursor"""
        from app.services.kg_adapter import ZepCloudAdapter
        import inspect

        sig = inspect.signature(ZepCloudAdapter.get_nodes)
        params = list(sig.parameters.keys())
        assert 'graph_id' in params
        assert 'limit' in params
        assert 'cursor' in params

    def test_get_edges_signature(self):
        """Test get_edges accepts graph_id, limit and cursor"""
        from app.services.kg_adapter import ZepCloudAdapter
        import inspect

        sig = inspect.signature(ZepCloudAdapter.get_edges)
        params = list(sig.parameters.keys())
        assert 'graph_id' in params
        assert 'limit' in params
        assert 'cursor' in params


class TestGraphitiAdapterAPI:
    """Test GraphitiAdapter API signatures"""

    def test_create_graph_signature(self):
        """Test create_graph accepts graph_id and name"""
        from app.services.kg_adapter import GraphitiAdapter
        import inspect

        sig = inspect.signature(GraphitiAdapter.create_graph)
        params = list(sig.parameters.keys())
        assert 'graph_id' in params

    def test_add_episode_signature(self):
        """Test add_episode accepts graph_id and text"""
        from app.services.kg_adapter import GraphitiAdapter
        import inspect

        sig = inspect.signature(GraphitiAdapter.add_episode)
        params = list(sig.parameters.keys())
        assert 'graph_id' in params
        assert 'text' in params

    def test_add_episodes_batch_signature(self):
        """Test add_episodes_batch accepts graph_id and texts"""
        from app.services.kg_adapter import GraphitiAdapter
        import inspect

        sig = inspect.signature(GraphitiAdapter.add_episodes_batch)
        params = list(sig.parameters.keys())
        assert 'graph_id' in params
        assert 'texts' in params

    def test_search_signature(self):
        """Test search accepts graph_id, query and limit"""
        from app.services.kg_adapter import GraphitiAdapter
        import inspect

        sig = inspect.signature(GraphitiAdapter.search)
        params = list(sig.parameters.keys())
        assert 'graph_id' in params
        assert 'query' in params
        assert 'limit' in params


class TestAdapterFactory:
    """Test adapter factory function"""

    def test_factory_returns_adapter(self):
        """Test factory returns an adapter"""
        from app.services.kg_adapter import get_knowledge_graph_adapter

        adapter = get_knowledge_graph_adapter()
        assert adapter is not None

    def test_cloud_mode(self):
        """Test knowledge graph mode is valid"""
        from app.config import Config

        assert Config.KNOWLEDGE_GRAPH_MODE in ['cloud', 'local']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
