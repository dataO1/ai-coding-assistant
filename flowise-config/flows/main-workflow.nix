{ agents, models, urls, lib, flowiseLib }:

let
  chatInput = {
    id = "chatInput_0";
    type = "chatInput";
    data = { label = "Chat Input"; };
    position = { x = 250; y = 50; };
  };

  chatOutput = {
    id = "chatOutput_0";
    type = "chatOutput";
    data = { label = "Chat Output"; };
    position = { x = 250; y = 600; };
  };

  # Collect all nodes and edges from agents
  nodes = [ chatInput ]
    ++ [ agents.supervisor.node agents.codeExpert.node agents.knowledgeScout.node ]
    ++ [ chatOutput ];

  edges = builtins.concatLists [
    agents.supervisor.connections
    agents.codeExpert.connections
    agents.knowledgeScout.connections
  ];
in
{
  inherit nodes edges;
}
