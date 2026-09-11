"""Curated, non-sensitive words for human-readable one-time pairing codes."""

PAIRING_WORDS=tuple(dict.fromkeys("""
acorn actor adobe amber apple apron april arrow atlas autumn badge baker bamboo
banana basil basin basket beach beacon berry birch bird biscuit blanket bloom
blossom blue boat bonus book bottle breeze brick bridge bright brook broom brush
bucket button cabin cable cactus candle canoe canvas captain carrot castle cedar
chalk charm cherry chest circle citrus clock cloud clover coast cocoa comet coral
cotton creek crown crystal daisy dance dawn delta denim desert desk diamond dolphin
door dragon dream drum eagle earth echo elm ember engine fabric falcon family feather
fern field finch firefly flag flame flower flute forest fox frame frost garden gate
gem ginger glass globe gold grape grass green grove guitar harbor hazel heart hill
honey horizon horse island ivory jade jasmine kettle kiwi lagoon lake lantern lark
leaf lemon light lilac lime linen lion maple marble meadow melon mint mirror moon
morning moss mountain mouse music nectar north ocean olive orange orchid otter owl
paint panda paper peach pearl pebble pepper pine planet plum pocket pond poppy quartz
queen rabbit rain raven reef ribbon river robin rose ruby sail salmon sand satin
school shell shore silver sky slate snow sparrow spice spring spruce star stone storm
summer sun sunset swan table teal tiger timber tulip valley velvet violet water wave
willow wind winter wood zebra almond anchor angel antler arch artist ash avenue avocado
badger bagel balcony balloon barley barn bay bean beaver bell bench bicycle blossom
board breeze bronze bubble butterfly cafe canyon cardinal carpet cave cello cereal
chair cheese chestnut chick cinnamon clay cliff compass cookie copper crane cricket
cup daffodil deer dock dove dune dusk elmwood emerald fence fig fir flute forest
fountain gardenia gazelle glacier goose harbor harvest hawk heather heron holly iris
islet jacket juniper kayak kingfisher ladder ladybird lavender lighthouse lily loaf
lotus mango maplewood market marlin marsh meadowlark moonlight muffin navy nest oak
oasis orchard oyster paddle palm paperclip parrot patch path peacock pear penguin
petal picnic pigeon pillow pinecone pitcher pony prism pumpkin rainbow reed robinwood
rocket rosemary sailboat sandal scarlet seed shadow sheep shelf skylark soap song
sparrowhawk spoon starfish strawberry stream sunflower sunrise tangerine teapot thorn
thrush tomato tower trail turtle umbrella vanilla village wagon walnut waterfall
whale wheat window woodland yarn yellow acrobat acacia airplane alder alpaca anise
ant applewood arctic armchair aspen aster badgework bakery barleycorn bayberry beehive
beetle blackberry bluebird blueberry boathouse bookshelf bow branch bread brookside
brown buttercup cabinwood canary candlestick caramel cat cedarwood cheerful chess
chestnutwood clamshell clear cobble coconut compassrose cornflower cottage cranberry
creekside crocus cupcake daylight dewdrop dragonfly driftwood duck earthstar evergreen
farm featherlight firelight flamingo flax foxtail freesia friendly gardenpath goldfinch
grapefruit greenhouse gull hammock happy hazelnut hedgehog hillside honeybee iceberg
indigo ink jasminewood jelly junebug kinglet lagoonblue lamb lemonwood linenfold
magpie marigold milkweed mist morningstar mossy nectarine nightingale nutmeg oaktree
oceanblue oatmeal opal orchardgate oriole paperboat parsley pawpaw peaceful peppercorn
pineapple play plumtree pondside porch primrose puffin quiet raccoon raindrop raspberry
redwood riverbank rosebud rowboat sailcloth sandpiper seaglass seashell seedling shade
shamrock shorebird skyblue snowdrop songbird starlight stonework strawberryfield sunny
sweetpea swift taffy tea thyme treetop trout vanilla beanbird wildflower windmill
wintergreen woodpecker wren zest airy alive ample aqua awake basic beige brave calm
careful clean clever coralred cozy crisp daily eager early easy fair gentle glad
golden grand happyhour hardy honest ideal jolly kind lively lucky merry mild neat
open peachy plain proud quick quietude ready rosy safe simple smart soft steady sunnyday
sweet tidy true useful vivid warm welcome wise young acornfield applecart autumnleaf
bakerstone beachgrass bellflower birdhouse bluebell bookshop bricklane brookfield
candlelight canoetrip cedarhill cherrywood clearwater cloverleaf coastland cottonwood
daisygate dawnlight dewdropper dreamland earthtone featherstone fernwood fieldstone
firewood flowerpot forestgate foxglove gardenwall gingerbread goldleaf grapevine
grassland greenfield grovepark harborlight hazelwood hilltop honeycomb islandbay
ivorywood jadegreen jasmineleaf kettlecorn kiwifruit lakeside lamplight larkspur
leaflet lemonleaf lilacwood limegreen linenwhite lionheart mapleleaf marblewood
meadowland melonseed mintleaf mirrorlake moonbeam mossgreen mountainview musicbox
nectarbird northstar oceanwave olivebranch orangeleaf orchidpink otterbay owltree
paintbrush pandabear paperkite peachstone pearlwhite pebblepath pepperleaf pinewood
planetblue plumtree pocketbook pondwater poppyfield quartzstone rabbitfoot raincloud
ravenwood reefstone ribbonwood riverstone robinred roseleaf rubyred sailcloth salmonpink
sandcastle satinwood schoolbell shellfish shoreline silverbell skyward slateblue
snowball sparrowtail spicejar springtime sprucetree starbright stonebridge stormcloud
summertime sunflowerseed sunrisegold swanlake tabletop tealblue tigerlily timberland
tulipfield valleyview velvetleaf violetblue waterlily wavecrest willowtree windchime
winterberry woodcraft zebrastripe
""".split()))

if len(PAIRING_WORDS)<512 or len(PAIRING_WORDS)!=len(set(PAIRING_WORDS)):
    raise RuntimeError('Pairing word list must contain at least 512 distinct words')
