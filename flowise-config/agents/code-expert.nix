{ models, urls }:

{
  node = {
    id = "codeExpert_0";
    type = "agent";
    label = "Code Expert Worker";
    data = {
      model = models.codeAgent;
      temperature = 0.2;
      systemPrompt = ''
        You are a code expert. Generate, refactor, and optimize code.
        Use available tools to understand existing code before generating.
      '';
      tools = [ "readFileAST" "lspNavigate" "getGitHistory" "lintCode" ];
      ollama_base_url = urls.ollama;
    };
    position = { x = 100; y = 400; };
  };

  connections = [
    { source = "supervisor_0"; target = "codeExpert_0"; }
  ];
}
