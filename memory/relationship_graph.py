# memory/relationship_graph.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Tracks every relationship in the world using a directed graph.
#
# WHAT IS A DIRECTED GRAPH?
#   A graph is a network of nodes (entities) connected by edges (relationships).
#   "Directed" means A→B can differ from B→A.
#   Example: The player may consider a merchant a "trusted friend" (sentiment +0.8),
#            but the merchant only sees the player as a "good customer" (sentiment +0.3).
#
# RELATIONSHIP TYPES SUPPORTED:
#   ally, enemy, romantic, employer, employee, rival, family, mentor, student,
#   neutral, feared_by, worships, commands, serves, trading_partner, at_war
#
# SENTIMENT SCALE:
#   -1.0 = deep hatred / sworn enemies
#   -0.5 = hostile / unfriendly
#    0.0 = neutral / indifferent
#   +0.5 = friendly / positive
#   +1.0 = deep love / absolute loyalty
#
# LOCATION: dnd_ai_dm/memory/relationship_graph.py
# ─────────────────────────────────────────────────────────────────────────────

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import networkx as nx

import config

# Path to the graph JSON file on disk
GRAPH_FILE = os.path.join(config.WORLD_DIR, 'relationship_graph.json')


class RelationshipGraph:
    """
    Manages all relationships between entities in the DnD world.
    Uses NetworkX DiGraph (directed graph) serialized to JSON for persistence.

    Entities can be: characters, factions, or nations.
    All relationships are directional and carry sentiment scores and history notes.
    """

    def __init__(self):
        """
        Loads the relationship graph from disk, or creates a new empty graph
        if no save file exists (first run).
        """
        self.graph: nx.DiGraph = self._load()

    def _load(self) -> nx.DiGraph:
        """
        Deserializes the graph from the JSON file using NetworkX's
        node_link_graph format. Creates a new empty DiGraph if no file exists.
        """
        if os.path.exists(GRAPH_FILE):
            with open(GRAPH_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return nx.node_link_graph(data, directed=True, multigraph=False)
        return nx.DiGraph()

    def save(self):
        """
        Serializes the entire graph to JSON and writes it to disk.
        Called automatically after every modification.
        node_link_data() converts the graph into a JSON-serializable dict.
        """
        with open(GRAPH_FILE, 'w', encoding='utf-8') as f:
            json.dump(nx.node_link_data(self.graph), f, indent=2)

    # ── Entity Node Methods ────────────────────────────────────────────────

    def add_entity(self, entity_id: str, entity_type: str, name: str, **extra_attrs):
        """
        Adds a node to the graph representing an entity in the world.

        Parameters:
          entity_id   — Unique ID string (should match the WorldState ID)
          entity_type — 'character', 'faction', or 'nation'
          name        — Display name used in summaries and prompts
          extra_attrs — Any additional attributes to store on the node
                        (e.g., faction='Thieves Guild', title='King')
        """
        self.graph.add_node(
            entity_id,
            type=entity_type,
            name=name,
            **extra_attrs
        )
        self.save()

    def entity_exists(self, entity_id: str) -> bool:
        """Returns True if the entity is already a node in the graph."""
        return self.graph.has_node(entity_id)

    # ── Relationship Edge Methods ──────────────────────────────────────────

    def set_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        sentiment: float,
        notes: str = '',
        current_date: str = ''
    ):
        """
        Creates or updates a directed relationship from one entity to another.

        Parameters:
          from_id      — ID of the entity that holds this relationship perspective
          to_id        — ID of the target entity
          rel_type     — Relationship category string (see module docstring)
          sentiment    — Float from -1.0 (hatred) to +1.0 (deep loyalty)
                         Automatically clamped to valid range.
          notes        — Free-text history/context for this relationship.
                         The DM appends to this as the story develops.
          current_date — In-game date string when this relationship was set/updated.

        If the edge already exists, all fields are updated.
        If it's new, a 'created' timestamp is also stored.
        """
        # Clamp sentiment to the valid -1.0 to +1.0 range
        clamped_sentiment = max(-1.0, min(1.0, sentiment))

        if self.graph.has_edge(from_id, to_id):
            # Update existing relationship edge
            edge = self.graph[from_id][to_id]
            edge['type'] = rel_type
            edge['sentiment'] = clamped_sentiment
            edge['notes'] = notes
            edge['last_updated'] = current_date
        else:
            # Create new relationship edge with creation timestamp
            self.graph.add_edge(
                from_id,
                to_id,
                type=rel_type,
                sentiment=clamped_sentiment,
                notes=notes,
                created=current_date,
                last_updated=current_date
            )
        self.save()

    def update_sentiment(self, from_id: str, to_id: str, delta: float, reason: str = ''):
        """
        Adjusts an existing relationship's sentiment by a delta value.
        Useful for incremental changes (e.g., a betrayal: delta=-0.4).

        If the relationship doesn't exist yet, creates a neutral one first.

        Parameters:
          delta  — Amount to add (positive) or subtract (negative) from sentiment.
          reason — Optional note appended to the relationship history.
        """
        if not self.graph.has_edge(from_id, to_id):
            # Create a neutral relationship baseline before adjusting
            self.set_relationship(from_id, to_id, 'neutral', 0.0)

        edge = self.graph[from_id][to_id]
        new_sentiment = max(-1.0, min(1.0, edge['sentiment'] + delta))
        edge['sentiment'] = new_sentiment

        # Append reason to notes if provided
        if reason:
            existing_notes = edge.get('notes', '')
            edge['notes'] = f"{existing_notes} | {reason}".strip(' |')

        self.save()

    def get_relationship(self, from_id: str, to_id: str) -> dict:
        """
        Returns the relationship data dict for from_id → to_id.
        If no relationship exists, returns a default neutral dict.
        """
        if self.graph.has_edge(from_id, to_id):
            return dict(self.graph[from_id][to_id])
        return {
            'type': 'neutral',
            'sentiment': 0.0,
            'notes': 'No established relationship.',
            'created': '',
            'last_updated': ''
        }

    def get_all_relationships(self, entity_id: str) -> list[dict]:
        """
        Returns all outgoing relationships for a given entity.
        Each item in the list includes the target entity's name and all edge data.

        Used by context_builder to tell the DM how an entity feels about others.
        """
        relationships = []
        for _, target_id, data in self.graph.out_edges(entity_id, data=True):
            # Look up the target's display name from the node attributes
            target_name = self.graph.nodes[target_id].get('name', target_id)
            relationships.append({
                'target_id': target_id,
                'target_name': target_name,
                **data
            })
        return relationships

    def get_mutual_relationship(self, id_a: str, id_b: str) -> dict:
        """
        Returns both sides of a relationship between two entities.
        Useful for determining how a two-way interaction will play out.

        Returns:
          {
            'a_to_b': { ...relationship data... },
            'b_to_a': { ...relationship data... }
          }
        """
        return {
            'a_to_b': self.get_relationship(id_a, id_b),
            'b_to_a': self.get_relationship(id_b, id_a)
        }

    # ── Prompt Formatting Methods ──────────────────────────────────────────

    def _sentiment_to_word(self, sentiment: float) -> str:
        """Converts a sentiment float to a human-readable descriptor."""
        if sentiment <= -0.75:
            return 'deeply hostile / sworn enemy'
        elif sentiment <= -0.4:
            return 'hostile'
        elif sentiment <= -0.1:
            return 'cold / unfriendly'
        elif sentiment <= 0.1:
            return 'neutral'
        elif sentiment <= 0.4:
            return 'friendly'
        elif sentiment <= 0.7:
            return 'trusting / warm'
        else:
            return 'deeply loyal / devoted'

    def summarize_for_prompt(self, entity_id: str) -> str:
        """
        Generates a natural-language summary of all of an entity's relationships.
        This text is injected directly into the DM's system prompt so the AI
        knows how this character/nation feels about everyone they know.

        Example output:
          - Guard Captain Hern: employer (trusting / warm) — Respects his discipline.
          - Thieves Guild: enemy (deeply hostile) — They burned his shop down.
        """
        rels = self.get_all_relationships(entity_id)
        if not rels:
            return 'No established relationships on record.'

        lines = []
        for r in rels:
            sentiment_word = self._sentiment_to_word(r.get('sentiment', 0.0))
            rel_type = r.get('type', 'unknown')
            notes = r.get('notes', '')
            target = r.get('target_name', r.get('target_id', 'Unknown'))
            line = f"  - {target}: {rel_type} ({sentiment_word})"
            if notes and notes != 'No established relationship.':
                line += f" — {notes}"
            lines.append(line)

        return '\n'.join(lines)

    def get_entity_name(self, entity_id: str) -> str:
        """Returns the display name of an entity node, or the ID if not found."""
        return self.graph.nodes[entity_id].get('name', entity_id) if self.entity_exists(entity_id) else entity_id
