{ models, urls }:

{
  node = {
    id = "supervisor_0";
    type = "agent";
    label = "Supervisor (Router)";
    data = {
      model = models.supervisor;
      temperature = 0.0;
      systemPrompt = ''
        You are a task router. Classify queries as:
        - CODE_TASK: Modify/generate code
        - LOOKUP_TASK: Research best practices
        - HYBRID_TASK: Both

        Respond with CodeExpert, KnowledgeScout, or HYBRID.
      '';
      ollama_base_url = urls.ollama;
    };
    position = { x = 250; y = 200; };
  };

  connections = [
    { source = "chatInput_0"; target = "supervisor_0"; }
    { source = "supervisor_0"; target = "chatOutput_0"; }
  ];
}
