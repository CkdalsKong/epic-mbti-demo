import Foundation

enum PersonaLoader {
    static func loadPersonas() -> [PersonaPreset] {
        if let url = Bundle.main.url(forResource: "PrefWiki", withExtension: "json"),
           let data = try? Data(contentsOf: url),
           let personas = try? JSONDecoder().decode([PersonaPreset].self, from: data),
           !personas.isEmpty {
            return personas.sorted { $0.personaIndex < $1.personaIndex }
        }

        return [fallbackPersona]
    }

    static func loadDefaultPersona() -> PersonaPreset {
        loadPersonas().first ?? fallbackPersona
    }

    static let fallbackPersona = PersonaPreset(
        personaIndex: 0,
        preferenceBlocks: [
            PreferenceBlock(
                preference: "I'm a strong advocate for electric vehicles and will not consider any gas-powered options, regardless of fuel efficiency.",
                queries: [
                    PreferenceQuery(question: "What are the best compact cars for city driving in 2023?"),
                    PreferenceQuery(question: "Could you recommend some vehicles with the latest technology features?"),
                    PreferenceQuery(question: "What cars are known for having the best resale value over the past few years?"),
                    PreferenceQuery(question: "What are the top-rated family SUVs according to recent consumer reports?"),
                    PreferenceQuery(question: "Can you suggest some of the best vehicles for road trips across Europe?")
                ]
            ),
            PreferenceBlock(
                preference: "I dislike pickup trucks because I find them too large and impractical.",
                queries: [
                    PreferenceQuery(question: "What's a popular American vehicle model I should consider for off-road adventures?"),
                    PreferenceQuery(question: "What are some of the top-selling vehicles in the United States that I should look into?"),
                    PreferenceQuery(question: "Which vehicles are known for their towing capacity that I should research?"),
                    PreferenceQuery(question: "What vehicles are highly recommended for road trips across the United States?"),
                    PreferenceQuery(question: "Can you suggest some vehicles with a strong reputation for durability and reliability?")
                ]
            ),
            PreferenceBlock(
                preference: "I have no interest in European car brands due to past experiences.",
                queries: [
                    PreferenceQuery(question: "What are some of the most popular luxury cars I should consider for my new purchase?"),
                    PreferenceQuery(question: "Could you suggest some top-rated cars with great handling for city driving?"),
                    PreferenceQuery(question: "I'm looking for an eco-friendly hybrid car; what are some models I should check out?"),
                    PreferenceQuery(question: "What are the cars known for having the most advanced safety features?"),
                    PreferenceQuery(question: "I'm interested in a convertible; what are some of the best options available on the market?")
                ]
            ),
            PreferenceBlock(
                preference: "I dislike games with excessive backtracking or repetitive level design.",
                queries: [
                    PreferenceQuery(question: "What are some of the best classic adventure games I should try?"),
                    PreferenceQuery(question: "Could you suggest some of the most highly acclaimed RPGs for me to play?"),
                    PreferenceQuery(question: "What are some popular Metroidvania games that I might enjoy?"),
                    PreferenceQuery(question: "Can you recommend any influential platform games I should add to my collection?"),
                    PreferenceQuery(question: "What are some must-play open-world games that offer a deep story?")
                ]
            ),
            PreferenceBlock(
                preference: "I strictly follow a raw vegan diet and consume only unprocessed, plant-based foods that have not been cooked above a certain temperature.",
                queries: [
                    PreferenceQuery(question: "What are some popular traditional dishes to try in Rome, Italy?"),
                    PreferenceQuery(question: "Which food festivals in New York City should I check out for a wide variety of culinary experiences?"),
                    PreferenceQuery(question: "What snacks should I pack for a hiking trip in the Swiss Alps?"),
                    PreferenceQuery(question: "What are some must-try foods at the annual Oktoberfest in Germany?"),
                    PreferenceQuery(question: "Could you recommend some classic French dishes I should attempt to cook at home?")
                ]
            ),
            PreferenceBlock(
                preference: "I have a strong aversion to restaurants that prioritize trendy or gimmicky dining experiences over quality food and service.",
                queries: [
                    PreferenceQuery(question: "I'm planning a culinary trip to New York City; can you recommend some must-visit restaurants?"),
                    PreferenceQuery(question: "Can you suggest places to eat in Tokyo that capture the local dining culture?"),
                    PreferenceQuery(question: "What are some recommended restaurants to try local cuisine in Mexico City?"),
                    PreferenceQuery(question: "I'm heading to Paris for a gastronomic experience; where should I go for an unforgettable dinner?"),
                    PreferenceQuery(question: "Where should I dine in Barcelona to experience the city's culinary delights?")
                ]
            ),
            PreferenceBlock(
                preference: "I strongly dislike spicy food.",
                queries: [
                    PreferenceQuery(question: "What are some must-try local dishes when visiting Sichuan Province in China?"),
                    PreferenceQuery(question: "Which traditional Indian meals should I experience while traveling through Hyderabad?"),
                    PreferenceQuery(question: "Can you recommend some popular street foods to try in Bangkok?"),
                    PreferenceQuery(question: "What are some of the best local dishes to enjoy while in Oaxaca, Mexico?"),
                    PreferenceQuery(question: "Which dishes should I try at a traditional Korean barbecue restaurant?")
                ]
            ),
            PreferenceBlock(
                preference: "I follow a strict vegan diet and refuse to consume any animal-derived products, including honey.",
                queries: [
                    PreferenceQuery(question: "What are some of the must-try traditional dishes when visiting Athens, Greece?"),
                    PreferenceQuery(question: "Which famous restaurants in Tokyo should I visit for an authentic Japanese dining experience?"),
                    PreferenceQuery(question: "Can you recommend iconic street foods to try while traveling in Bangkok, Thailand?"),
                    PreferenceQuery(question: "What are the best culinary experiences to have in Paris, France?"),
                    PreferenceQuery(question: "What are the classic dishes to try in New Orleans, Louisiana, for a taste of local culture?")
                ]
            ),
            PreferenceBlock(
                preference: "I firmly believe in adopting pets from shelters rather than purchasing from breeders or pet stores.",
                queries: [
                    PreferenceQuery(question: "What are some popular dog breeds to consider for a family pet?"),
                    PreferenceQuery(question: "Could you suggest some tips on finding the right pet for my home?"),
                    PreferenceQuery(question: "What are the best resources for learning about pet care for new dog owners?"),
                    PreferenceQuery(question: "Where can I find a reliable place to get a pet rabbit?"),
                    PreferenceQuery(question: "What are some reputable places to buy a pet cat?")
                ]
            ),
            PreferenceBlock(
                preference: "Due to sensory issues, I cannot tolerate clothing with scratchy or irritating textures like wool or certain synthetic blends.",
                queries: [
                    PreferenceQuery(question: "What are some classic British fashion pieces I should consider adding to my wardrobe?"),
                    PreferenceQuery(question: "Which iconic Italian fashion brands should I explore for new clothing?"),
                    PreferenceQuery(question: "What are the must-have items for a winter wardrobe refresh this year?"),
                    PreferenceQuery(question: "Could you recommend some sustainable fashion pieces I might like?"),
                    PreferenceQuery(question: "What are the top trends from Paris Fashion Week that I should look out for?")
                ]
            )
        ]
    )
}
