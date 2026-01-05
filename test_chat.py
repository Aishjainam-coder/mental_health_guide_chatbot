from main import chat, client, ChatRequest

# Return a structured JSON-like reply string the way the model will
class M:
    content='{"technical":"t","realistic":"r","emotional":"e"}'

# Test crisis detection
class M2:
    content='{"technical":"","realistic":"","emotional":"If you are in immediate danger, call emergency services."}'

class C2:
    message=M2()

class R2:
    choices=[C2()]

class C:
    message=M()

class R:
    choices=[C()]

# Monkeypatch
class FakeCompletions:
    @staticmethod
    def create(*a, **k):
        return R()

class FakeChat:
    completions = FakeCompletions()

client.chat = FakeChat()

resp = chat(ChatRequest(user_id='testuser', message='Hello beginner'))
print('technical=', resp['reply']['technical'])
print('realistic=', resp['reply']['realistic'])
print('emotional=', resp['reply']['emotional'])
