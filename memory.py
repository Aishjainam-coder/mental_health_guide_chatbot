user_memory = {}

def get_memory(user_id):
    return user_memory.get(user_id, {})

def update_memory(user_id, data):
    if user_id not in user_memory:
        user_memory[user_id] = {}
    user_memory[user_id].update(data)
