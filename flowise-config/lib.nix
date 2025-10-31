# Shared utilities for building Flowise nodes
{
  mkNode = { id, type, label, data, position }:
    {
      inherit id type;
      data = data // { inherit label name; name = id; };
      inherit position;
    };

  mkEdge = { source, target, sourceHandle ? null, targetHandle ? null }:
    {
      inherit source target;
    } // (if sourceHandle != null then { sourceHandle } else {})
      // (if targetHandle != null then { targetHandle } else {});
}
