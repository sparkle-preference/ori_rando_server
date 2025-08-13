from models import Seed, User, client

with client.context():
    query = Seed.query(Seed.temp_user == None)
    #del Seed.temp_user
    #del Seed._properties["User"]
    for seed in query:
        if not seed.legacy_author_key and not seed.author_key:
            matching_user_query = User.query(User.name == seed.author).fetch()

            if len(matching_user_query) == 1:
                author = matching_user_query[0]
                new_seed = Seed(
                    id="%s:%s" % (author.key.id(), seed.name),
                    placements = seed.placements,
                    flags = seed.flags,
                    hidden = seed.hidden,
                    description = seed.description,
                    players = seed.players,
                    author_key = author.key,
                    author = seed.author,
                    name = seed.name
                    )
                new_seed._clone_properties()
                del new_seed._properties["User"]
                new_seed.put()
                seed.key.delete()
                
                print(f"seed {seed.key} -> user {new_seed.key}")
                
