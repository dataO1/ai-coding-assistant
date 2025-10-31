{ models, urls }:

{
  node = {
    id = "knowledgeScout_0";
    type = "agent";
    label = "Knowledge Scout Worker";
    data = {
      model = models.knowledge;
      temperature = 0.3;
      systemPrompt = ''
        You are a research specialist. Search documentation and synthesize findings.
        Compress results to max 1000 tokens.
      '';
      tools = [ "webSearch" "searchDocs" "summarizeFindings" ];
      ollama_base_url = urls.ollama;
    };
    position = { x = 400; y = 400; };
  };

  connections = [
    { source = "supervisor_0"; target = "knowledgeScout_0"; }
  ];
}
