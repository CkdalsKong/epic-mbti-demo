import Foundation

enum SampleArticles {
    static let automobile = WikiArticle(
        pageID: -1,
        title: "Automobile",
        extract: """
        An automobile is a road vehicle that usually has four wheels and is designed primarily for passenger transportation. Most automobiles in the twentieth century were powered by internal combustion engines using gasoline or diesel fuel, although steam cars and early electric cars also appeared in the history of road transport.

        Battery electric vehicles use one or more electric motors powered by rechargeable battery packs. Modern electric cars are often discussed in terms of driving range, charging infrastructure, battery chemistry, purchase price, and the environmental impact of electricity generation. Plug-in hybrid vehicles combine an electric drivetrain with a gasoline engine, while fully electric vehicles avoid tailpipe emissions altogether.

        Pickup trucks are light-duty vehicles with an enclosed cab and an open cargo bed. They are popular in North America for towing, hauling, construction work, and off-road recreation. Full-size pickup trucks can be large and heavy compared with compact cars, and their size can affect parking, city driving, and everyday practicality.

        European car manufacturers such as Volkswagen, BMW, Mercedes-Benz, Peugeot, Renault, Fiat, Audi, Porsche, and Volvo have influenced automobile design, safety systems, motorsport, luxury branding, and small-car engineering. Some buyers compare European models with Japanese, Korean, and American vehicles when considering maintenance costs and resale value.

        Sport utility vehicles and crossovers are often marketed for family use because they provide cargo space, elevated seating positions, and all-wheel-drive options. Safety ratings, driver-assistance technology, child-seat access, and long-distance comfort are common factors in SUV recommendations.

        Automobile recommendations can be affected by personal constraints. A user who refuses gas-powered options may need electric-only suggestions, charging considerations, and information about battery-electric availability. A user who dislikes pickup trucks may need alternatives for hauling or road trips. A user uninterested in European car brands may prefer recommendations from other regions.

        Restaurants, food, clothing, video games, and pet adoption are unrelated to most automobile pages, but a personal device can encounter all of these topics in a mixed browsing history. Indiscriminate indexing stores every chunk from every page, while preference-aligned memory construction keeps only the pieces that can help future personalized answers.
        """,
        source: .sample
    )
}
