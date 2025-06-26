-class ProductTools:
-    """Define Product Agent functions (tools)"""
-    agent_name = AgentType.PRODUCT.value
+class EvidenceTools:
+    """Tools CasefileAgent uses for exhibit & fact management."""
+    agent_name = AgentType.CASEFILE.value

-    @kernel_function(description="Add an extras pack/new product …")
-    async def add_mobile_extras_pack(...):
-        ...
+    @kernel_function(description="Search exhibits for a key phrase.")
+    async def search_exhibits(phrase: str, top_k: int = 5) -> str:
+        return (
+            f"Placeholder: top {top_k} exhibits containing “{phrase}”. "
+            "Replace with /casefile/query call."
+        )

+    @kernel_function(description="Add a fact to the timeline.")
+    async def add_fact(fact_text: str, exhibit_id: str) -> str:
+        return "Placeholder: fact added and linked to exhibit."

+    @kernel_function(description="Get a chronological fact timeline.")
+    async def get_fact_timeline() -> str:
+        return "Placeholder timeline."
