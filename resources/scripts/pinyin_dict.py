#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pinyin_dict.py - 零依赖中华古典文献汉字拼音与层级编号引擎

提供高鲁棒性、零外部依赖的拼音与中文数字转换服务：
1. 涵盖 3,500+ 常用规范汉字与经典术数、文献学专有名词
2. 经典多音字辨析（乾坤 qian-kun, 五行 wu-xing, 长生 chang-sheng, 徐乐吾 xu-le-wu 等）
3. 优雅的中文卷数/章节序号转换（卷一 -> juan-01, 卷二十三 -> juan-23）
4. 支持用户自定义配置覆盖（通过 classics_config.json 或字典注入）
"""

import json
import re
from pathlib import Path
from typing import Dict, Optional, Any, List

# 拼音音节全量汉字映射表
SYLLABLE_MAP: Dict[str, str] = {
    "a": "阿啊呵腌嗄吖",
    "ai": "爱矮挨哎碍癌艾唉哀蔼隘埃皑呆嗌嫒瑷暧捱锿",
    "an": "安按暗岸案俺氨鞍谙庵鹌黯埯广",
    "ang": "昂盎肮",
    "ao": "奥傲熬凹袄懊遨敖翱嗷拗坳獒嚣鳌",
    "ba": "把八吧拔霸罢爸坝芭跋靶巴拔疤钯笆伯拔菝魃",
    "bai": "百白摆败柏拜佰稗败",
    "ban": "半办班般板版伴扮拌斑搬钣瘢瓣",
    "bang": "帮傍棒邦榜绑膀镑梆谤蚌磅",
    "bao": "包抱报饱保暴薄胞宝爆苞葆豹刨褒雹鲍煲褓趵",
    "bei": "被北倍杯背碑贝悲备辈惫臂卑悖蓓焙狈邶",
    "ben": "本奔笨苯夯畚坌",
    "beng": "崩蹦绷泵迸嘣",
    "bi": "比必避闭笔壁币碧毕彼辟逼臂庇鄙毙痹弊璧匕秘婢蔽弼愎哔睥妣毖筚",
    "bian": "边变便编扁辩变辨遍鞭匾贬弁砭辫变",
    "biao": "表标彪膘镖飙裱骠镳俵鳔",
    "bie": "别憋鳖瘪蹩",
    "bin": "宾斌濒彬缤槟鬓殡",
    "bing": "并病冰丙屏兵柄饼炳禀并秉冰",
    "bo": "拨波伯薄泊博播脖驳舶帛勃跛簸搏蕃铂礴箔饽擘",
    "bu": "不部步布补捕埔埠簿卜哺怖堡钚",
    "ca": "擦嚓拆",
    "cai": "才菜财采材踩裁彩睬猜蔡",
    "can": "参残蚕餐惭惨灿孱骖飡",
    "cang": "藏仓苍沧舱伧",
    "cao": "草操槽草曹嘈糙漕",
    "ce": "策测册侧厕恻",
    "cen": "参岑涔",
    "ceng": "曾层蹭噌",
    "cha": "查察差茶插叉茬茶岔碴刹诧楂槎檫",
    "chai": "柴拆差钗豺",
    "chan": "产单阐颤掺蝉缠铲馋谄婵忏潺澶蒇单",
    "chang": "长常场唱敞肠尝偿倡猖畅倘裳嫦昌伥昶苌",
    "chao": "朝超抄炒钞巢吵潮嘲焯",
    "che": "车撤扯彻澈掣尺砗",
    "chen": "陈晨沉衬臣尘辰称趁嗔谌忱抻宸琛",
    "cheng": "成程称城承惩橙成乘撑澄呈诚呈盛骋秤铖铛",
    "chi": "吃尺持赤池翅迟痴驰耻匙哧嗤饬弛墀叱啻踟",
    "chong": "重充冲虫崇宠涌忡憧铳舂",
    "chou": "抽愁丑仇筹酬绸稠臭瞅俦畴 Chou 惆",
    "chu": "出除处初楚础触储厨橱雏黜躇搐蜍楮樗",
    "chua": "欻",
    "chuai": "揣踹嘬",
    "chuan": "穿传船串川喘椽舛钏",
    "chuang": "创床窗闯疮幢怆",
    "chui": "吹垂锤炊陲棰",
    "chun": "春纯唇春醇椿蠢莼",
    "chuo": "戳绰辍啜龊",
    "ci": "此词辞刺次瓷磁雌慈赐伺茨疵祠差茈",
    "cong": "从聪丛葱匆淙骢璁",
    "cou": "凑辏",
    "cu": "促粗醋卒簇蹙徂猝蹴",
    "cuan": "窜攒篡撺蹿爨",
    "cui": "催脆摧粹翠衰崔萃瘁悴",
    "cun": "村存寸蹲忖",
    "cuo": "错措搓挫撮嵯厝磋蹉",
    "da": "大大打达答搭瘩耷靼哒",
    "dai": "代带待袋戴呆逮贷歹怠黛殆怠",
    "dan": "但单担石蛋淡胆弹旦氮耽旦诞啖惮澹殚萏",
    "dang": "当党挡荡档宕铛谠",
    "dao": "到道导倒刀岛盗稻捣祷悼叨",
    "de": "的得德底地",
    "dei": "得",
    "deng": "等登灯邓凳澄蹬瞪噔",
    "di": "地的第低底弟帝敌递滴提帝蒂抵缔邸睇荻狄氐砥籴",
    "dian": "电点店典垫颠奠碘殿掂淀滇玷踮巅簟甸",
    "diao": "掉条调掉吊钓雕凋碉叼",
    "die": "叠跌爹碟谍蝶喋耋牒蹀",
    "ding": "定订顶丁鼎钉盯叮町酊锭啶",
    "diu": "丢",
    "dong": "东西动冬懂洞冻栋董恫咚",
    "dou": "都斗豆兜抖抖逗窦读陡蚪",
    "du": "度都读督毒独肚渡赌堵妒睹杜牍笃渎髑",
    "duan": "段短断端锻缎椴煅",
    "dui": "对队堆兑敦碓",
    "dun": "顿顿吨盾蹲敦敦钝盹沌趸",
    "duo": "多朵夺舵度跺堕惰哆咄掇哚柁",
    "e": "恶俄饿鹅额阿峨蛾扼娥愕遏讹垩萼厄",
    "ei": "诶",
    "en": "恩嗯摁",
    "er": "而二儿尔耳饵贰迩洱",
    "fa": "发法罚乏伐阀筏发珐",
    "fan": "反饭翻番犯凡繁返范泛贩帆矾藩梵燔",
    "fang": "方放房防访纺仿坊芳妨肪舫邡",
    "fei": "非飞肥费废匪沸菲啡扉霏翡妃诽狒",
    "fen": "分份纷粉芬愤粪坟汾焚氛分吩",
    "feng": "风封逢缝丰峰锋疯奉枫蜂讽冯烽俸",
    "fo": "佛",
    "fou": "否缶",
    "fu": "服务复夫负父付富赋妇府附服辅佛副幅伏福浮符抚腐腹腐赴覆抚扶辐袱孵涪拂袱芙俘匐敷腑麸赙孚苻",
    "ga": "旮尬嘎噶",
    "gai": "该改盖概钙芥丐赅垓",
    "gan": "干感敢赶甘竿肝柑乾赶秆苷尴尬矸疳",
    "gang": "刚刚钢港岗纲杠缸肛冈罡",
    "gao": "高告搞稿膏羔糕睾镐诰杲缟",
    "ge": "个各哥割歌隔革格阁各葛鸽搁疙铬仡咯",
    "gei": "给",
    "gen": "跟根亘茛",
    "geng": "更耕颈庚羹耿梗埂",
    "gong": "工公共供红功攻宫巩贡拱恭躬共肱汞篝蚣",
    "gou": "够购勾构狗钩沟苟垢苟枸缑觏",
    "gu": "古股故顾固骨谷姑估孤辜菇菇箍蛊贾沽毂鸪咕蛄汩瞽菰",
    "gua": "挂刮瓜寡褂括卦呱栝鸹",
    "guai": "怪拐乖",
    "guan": "关管观馆官冠灌贯惯棺莞纶盥鹳",
    "guang": "光广逛潢胱",
    "gui": "归鬼贵规桂轨柜诡硅龟跪癸柜刽傀闺晷皈簋",
    "gun": "滚棍衮绲",
    "guo": "国过果裹郭锅涡蝈埚",
    "ha": "哈哈蛤虾",
    "hai": "海还害孩嗨骸咳亥",
    "han": "看喊寒汗汉含旱涵捍撼憨酣罕函韩焊颔邯",
    "hang": "行巷航夯杭沆",
    "hao": "好号毫豪耗浩皓郝蒿壕嚆",
    "he": "和合何喝河核贺褐赫呵荷鹤盒禾涸阂劾壑诃",
    "hei": "黑嘿",
    "hen": "很大很恨痕",
    "heng": "横恒哼衡蘅桁",
    "hong": "红洪轰哄虹宏烘鸿弘泓",
    "hou": "后候厚猴喉吼侯逅篌猴",
    "hu": "乎互呼护户湖胡虎狐核糊忽蝴葫沪弧壶琥猢唿扈鹄斛笏",
    "hua": "话花化画华划滑哗豁桦骅砉",
    "huai": "坏怀淮槐",
    "huan": "换还欢环缓患唤幻还原痪寰焕豢涣桓洹",
    "huang": "黄荒皇慌晃谎煌璜簧凰幌惶徨湟",
    "hui": "会回挥汇灰惠辉徽毁晦慧悔秽贿卉晦蛔晖麾彗茴",
    "hun": "混昏魂婚浑荤馄诨",
    "huo": "或活火获货伙惑霍祸豁夥藿",
    "ji": "机制计极级给基机集吉纪济记济技术击即继季寄急籍疾绩技挤辑脊齐鸡剂迹姬畸饥寂箕祭戟羁嵇唧畿汲即疾藉霁稷",
    "jia": "家加价假甲架驾稼嫁嘉夹挟枷颊钾贾枷镓袈",
    "jian": "见间建件简坚检减兼渐键荐监剪健剑鉴践检贱碱奸歼笺溅拣坚煎茧箭简菅锏蹇戬",
    "jiang": "将强江讲降奖僵蒋疆浆姜匠酱浆豇礓",
    "jiao": "教交角较叫脚胶缴娇焦浇嚼矫郊搅骄窖狡饺剿跤蕉礁蛟椒湫侥峤",
    "jie": "结解接节街界借介捷阶截杰洁竭皆秸揭姐戒劫诫解 Jie 节孑诘玠碣",
    "jin": "进今近金仅紧津劲尽禁锦斤巾谨浸晋筋尽靳烬槿赆",
    "jing": "经精敬竞境静景警镜惊京径净井晶颈荆茎茎菁靓旌痉腈",
    "jiong": "窘炯迥扃",
    "jiu": "就九酒旧久救纠究九舅揪灸灸玖赳",
    "ju": "据局具居聚巨剧举车句拘拒距惧菊鞠狙驹疽沮炬桔咀矩锯踞趄踽琚",
    "juan": "卷圈倦绢捐眷镌涓鄄",
    "jue": "决绝觉角脚掘爵决诀抉崛倔獗攫噱矍",
    "jun": "均军君菌俊峻竣骏钧龟郡筠",
    "ka": "卡喀咖咯",
    "kai": "开凯慨楷锴揩恺铠",
    "kan": "看砍堪刊槛勘坎瞰龛",
    "kang": "康抗慷炕扛亢闶",
    "kao": "考靠烤拷铐",
    "ke": "可以可克科客刻渴课颗壳克服棵柯坷苛恪苛嗑咳氪稞珂钪",
    "ken": "肯垦恳啃",
    "keng": "坑铿",
    "kong": "空孔恐控箜",
    "kou": "口扣寇抠蔻",
    "ku": "苦枯哭裤库骷窟",
    "kua": "跨夸垮挎胯",
    "kuai": "块快会筷脍侩狯",
    "kuan": "宽款",
    "kuang": "况矿框匡狂旷筐眶诓",
    "kui": "亏奎愧馈溃魁葵盔窥匮夔逵睽",
    "kun": "困坤捆昆琨鲲髡",
    "kuo": "扩阔括廓",
    "la": "拉落啦辣蜡腊拉喇垃",
    "lai": "来赖莱睐籁赉",
    "lan": "蓝兰栏览烂懒浪篮拦婪岚澜揽缆榄褴斓",
    "lang": "浪郎狼朗廊啷琅锒",
    "lao": "老落捞劳牢老姥烙酪涝獠佬",
    "le": "了乐勒肋叻",
    "lei": "类累雷泪勒擂蕾儡磊镭",
    "leng": "冷楞棱",
    "li": "理力立利历例里离丽礼厉利李黎历璃隶吏莉栗励厘粒砾漓笠篱鲤沥戾荔傈骊喱栎郦猁",
    "lia": "俩",
    "lian": "连联练恋脸廉莲链帘敛怜琏莲濂裢臁",
    "liang": "两量良粮凉梁亮辆谅两椋魉",
    "liao": "了料疗聊僚辽燎寥缭辽镣撩獠",
    "lie": "列烈劣裂猎猎冽趔咧",
    "lin": "林临邻磷淋琳鳞霖凛吝遴檩嶙麟",
    "ling": "领令另零灵龄凌陵玲聆铃菱伶苓翎囹棂",
    "liu": "六流留刘柳溜硫瘤馏榴碌鎏",
    "long": "隆龙笼聋拢陇咙珑砻",
    "lou": "楼漏陋搂篓娄髅蝼",
    "lu": "路六陆录录露绿鲁炉芦卢颅掳卤虏辘漉禄轳鹿赂辂麓",
    "luan": "乱卵峦孪挛滦栾鸾",
    "lue": "略掠锊",
    "lun": "论轮伦沦纶仑囵",
    "luo": "落罗络洛锣骡螺裸络咯萝逻珞泺椤",
    "lv": "律旅绿率吕侣铝虑履屡氯缕闾榈偻",
    "ma": "吗么马妈麻骂抹码玛蚂摩嘛犸",
    "mai": "买卖麦迈脉埋蛮霾",
    "man": "满慢漫曼蛮瞒埋蔓馒缦幔蛮",
    "mang": "忙盲芒茫氓莽邙",
    "mao": "毛猫冒貌贸茅矛茂髦卯耄旄",
    "me": "么",
    "mei": "没美每煤妹眉梅魅妹枚昧镁玫酶袂霉",
    "men": "们门闷门扪",
    "meng": "蒙猛梦孟盟懵檬萌朦氓甍",
    "mi": "米密秘迷蜜弥觅眯糜泌靡谜谧芈",
    "mian": "面免绵眠勉缅棉面冕娩沔眄",
    "miao": "秒苗妙描庙瞄蔑渺邈淼",
    "mie": "灭蔑篾",
    "min": "民敏泯悯闽皿闵珉",
    "ming": "明名命鸣铭冥铭瞑",
    "miu": "谬",
    "mo": "么没模末磨默漠墨摸莫抹摩膜魔沫磨抹莫茉陌殁秣",
    "mou": "某谋眸缪哞",
    "mu": "目母木幕模募暮墓穆牧姥亩姆睦牡苜",
    "na": "那南哪拿纳呐钠娜捺",
    "nai": "奶乃耐奈鼐萘",
    "nan": "南难男喃楠赧",
    "nang": "囊馕曩",
    "nao": "脑闹恼挠淖孬",
    "ne": "呢哪讷",
    "nei": "内那馁",
    "nen": "嫩恁",
    "neng": "能",
    "ni": "你呢拟泥尼逆妮匿腻霓铌",
    "nian": "年念粘碾撵拈廿",
    "niang": "娘酿",
    "niao": "鸟尿袅",
    "nie": "捏涅聂摄镊镍孽啮",
    "nin": "您恁",
    "ning": "宁凝拧泞狞柠",
    "niu": "牛纽钮扭拗",
    "nong": "农浓弄脓侬",
    "nu": "怒奴努弩孥",
    "nuan": "暖",
    "nue": "虐疟",
    "nuo": "诺挪懦糯傩",
    "nv": "女衄",
    "o": "哦喔噢",
    "ou": "欧偶欧鸥呕殴藕沤",
    "pa": "怕爬啪帕扒耙杷",
    "pai": "派排拍牌迫徘湃蒎",
    "pan": "盘判攀盼潘盘叛畔拚磐蟠",
    "pang": "旁胖庞膀彷滂",
    "pao": "跑泡抛炮袍咆庖刨",
    "pei": "配培陪佩赔胚pei辔沛裴霈",
    "pen": "喷盆",
    "peng": "朋朋彭鹏捧碰碰蓬棚膨烹澎抨",
    "pi": "批皮疲披匹辟脾劈僻坯披毗啤痞砒霹丕邳纰",
    "pian": "片篇偏便骗蹁骈",
    "piao": "票漂飘瓢朴嫖瞟缥",
    "pie": "撇瞥氕",
    "pin": "品贫频拼聘颦",
    "ping": "平评瓶凭屏苹萍坪枰乒娉",
    "po": "破迫颇坡婆魄泼珀鄱繁",
    "pou": "剖掊",
    "pu": "普铺堡仆扑蒲扑谱铺埔瀑曝葡朴埔溥蹼",
    "qi": "起其气七期齐器妻奇戚漆弃企祈欺旗骑乞歧启泣契祺蹊祁凄葺柒琪琦沏杞",
    "qia": "恰卡掐洽",
    "qian": "前千钱潜牵浅乾签铅迁欠歉纤遣嵌虔堑黔骞浅掮钤",
    "qiang": "强抢枪墙腔戕锵襁",
    "qiao": "桥巧切俏桥侨悄瞧翘敲乔峭窍壳荞蕉雀硗侨",
    "qie": "且切窃怯惬妾挈锲",
    "qin": "亲琴侵勤擒寝秦芹琴沁禽钦衾",
    "qing": "情请清青轻倾顷氢晴卿庆青蜻罄",
    "qiong": "穷琼穹茕",
    "qiu": "求秋球丘仇囚裘邱蚯虬",
    "qu": "去区取曲屈趋趣驱渠躯曲娶岖瞿祛",
    "quan": "全权圈劝泉拳犬券痊诠醛",
    "que": "确却缺雀雀鹊炔榷阕",
    "qun": "群裙",
    "ran": "然燃染冉苒",
    "rang": "让嚷壤攘禳穰",
    "rao": "绕扰饶娆荛",
    "re": "热若惹",
    "ren": "人任认仁忍韧刃纫妊饪仞荏恁",
    "reng": "扔仍",
    "ri": "日",
    "rong": "容荣融蓉溶绒茸榕冗嵘",
    "rou": "肉柔揉揉糅",
    "ru": "如果入如乳儒辱汝濡茹孺褥",
    "ruan": "软阮",
    "rui": "瑞锐芮蕊蕤",
    "run": "润闰",
    "ruo": "若弱箬",
    "sa": "撒萨洒飒仨",
    "sai": "塞思赛鳃",
    "san": "三散伞叁糁",
    "sang": "桑丧嗓",
    "sao": "扫骚嫂臊缫",
    "se": "色色涩瑟啬",
    "sen": "森",
    "seng": "僧",
    "sha": "杀沙啥砂傻刹煞杉厦裟",
    "shai": "晒筛色",
    "shan": "山闪衫扇善陕单栅禅扇讪煽赡珊苫",
    "shang": "上商伤尚赏汤裳晌墒殇",
    "shao": "少烧绍勺哨梢稍邵韶鞘",
    "she": "社设摄射舌涉舍蛇奢赦赊慑歙",
    "shei": "谁",
    "shen": "什神深身申伸甚参慎审沈呻肾绅砷渗葚蜃",
    "sheng": "生成声胜升圣绳剩省盛笙甥牲昇",
    "shi": "是事实使始识世市时失示诗视史石室十施饰释式试适实食士势嗜湿氏誓噬侍侍嗜师施适释匙矢屎谥轼逝筮豕弑",
    "shou": "受手收首守授售寿兽瘦手首狩",
    "shu": "数书术树属述殊输束熟蔬舒署殊鼠庶薯梳叔枢抒殊暑淑赎墅恕梳沭菽",
    "shua": "刷耍",
    "shuai": "帅率摔甩蟀",
    "shuan": "栓闩拴",
    "shuang": "双霜爽爽",
    "shui": "水说谁税睡",
    "shun": "顺舜瞬",
    "shuo": "说数硕烁朔搠蒴",
    "si": "四死似司思私丝斯寺撕撕死饲赐祀嘶厮肆汜兕蛳",
    "song": "送松宋颂诵耸耸怂嵩崧",
    "sou": "搜艘搜叟嗽嗖薮",
    "su": "素速宿诉肃塑苏塑俗苏肃粟溯簌夙",
    "suan": "算酸蒜",
    "sui": "岁虽随碎随岁穗遂祟谇",
    "sun": "孙损笋荪隼",
    "suo": "所索缩锁琐唆娑挲羧",
    "ta": "他她它踏塔拓塌獭挞踏沓挞",
    "tai": "太台态胎泰苔抬台酞汰钛",
    "tan": "谈探炭弹坦坛贪叹毯瘫摊痰潭谭坍檀",
    "tang": "堂唐汤塘躺糖趟烫淌倘膛搪镗醣",
    "tao": "套逃陶桃讨淘涛萄焘韬绦",
    "te": "特忒忑",
    "teng": "腾疼滕藤",
    "ti": "提体题替啼梯剔惕涕踢嚏屉鹈",
    "tian": "天田填添甜舔恬殄畋",
    "tiao": "条挑跳调迢眺龆笤",
    "tie": "贴铁帖餮",
    "ting": "听停挺庭厅亭艇廷霆铤婷",
    "tong": "同通统痛童铜桐桶筒彤恫恸僮",
    "tou": "头投透偷骰",
    "tu": "土图突徒途涂吐屠秃兔荼",
    "tuan": "团推湍疃抟",
    "tui": "推退腿蜕褪颓",
    "tun": "吞屯囤褪豚臀",
    "tuo": "托脱妥拓拖椭驼拓唾鸵陀鼍柁",
    "wa": "挖瓦洼哇娃袜佤",
    "wai": "外歪",
    "wan": "完万晚湾丸玩腕宛挽顽挽碗丸婉惋菀绾",
    "wang": "望往王网忘亡旺妄汪惘罔",
    "wei": "为位未委微维卫围味魏尾威唯唯畏胃喂危巍韦尉纬萎伪娓帷苇渭嵬猥",
    "wen": "文问闻稳温吻蚊纹瘟紊汶",
    "weng": "翁嗡瓮",
    "wo": "我握窝卧挝沃蜗渥斡",
    "wu": "无五物午误舞武屋务乌吴物吾污亡巫侮伍戊恶侮晤坞妩钨毋捂蜈鹜",
    "xi": "系西席息希吸喜细析习喜戏洗洗夕稀悉溪惜嘻膝昔熙犀羲禧媳膝檄铣汐蹊淅蟋",
    "xia": "下夏狭峡吓辖暇瞎霞瑕匣厦虾黠",
    "xian": "现先线显险限县宪鲜纤闲仙陷咸献贤嫌弦铣掀娴涎舷馅羡 Xian",
    "xiang": "相应想向相象详香项乡降享箱翔祥巷像橡襄厢飨",
    "xiao": "小效校消销笑宵削晓萧硝嚣孝肖啸霄枭潇哮筱",
    "xie": "些写斜血鞋协携屑械歇泄谢泻懈卸解谐邪携协蝎颉缬",
    "xin": "心新信辛欣薪芯锌忻馨莘",
    "xing": "型行形星性省醒兴幸姓刑杏腥悻",
    "xiong": "雄胸兄凶熊汹芎",
    "xiu": "修秀休袖宿绣嗅锈朽羞咻溴",
    "xu": "需许续序虚徐叙蓄绪畜旭戌絮恤婿墟酗顼",
    "xuan": "选宣玄悬旋喧轩癣眩炫绚楦萱漩",
    "xue": "学雪血靴穴薛噱谑",
    "xun": "训讯迅巡寻循旬询逊熏殉汛勋徇驯浔",
    "ya": "压亚牙呀押讶哑雅崖鸭芽衙丫轧桠",
    "yan": "言严研验眼演沿烟岩宴盐延厌掩艳颜炎阎衍奄燕雁砚堰闫酽奄筵",
    "yang": "样养阳洋扬羊仰杨氧秧殃佯漾疡央",
    "yao": "要药么摇邀耀咬腰窑谣遥姚妖夭侥钥爻",
    "ye": "也业页夜野叶野爷液冶咽噎耶拽邺",
    "yi": "一以意已义议易医移依役移疑益异宜伊仪遗翼亿乙艺抑疫役忆怡谊溢壹裔颐逸佚邑倚旖",
    "yin": "因引音银印阴饮隐姻吟寅淫殷湮尹蚓",
    "ying": "应影英营迎映盈硬荧莹赢婴鹰樱蝇缨颍郢",
    "yo": "哟育唷",
    "yong": "用永拥勇涌泳咏庸雍蛹恿镛",
    "you": "有由又友油优右游幼诱尤邮犹忧幽佑酉釉铀疣",
    "yu": "于与予语育余域遇宇雨预玉欲玉鱼御欲愉余羽愈狱愈迂愚渝喻峪驭庾郁娱虞逾隅俞盂",
    "yuan": "元原远员院源圆愿缘援怨园苑渊冤垣辕沅媛鸳",
    "yue": "月越约跃阅乐岳钥悦樾粤",
    "yun": "运云员允均韵孕蕴匀晕陨酝郧",
    "za": "杂砸咋扎",
    "zai": "在再灾载仔栽宰",
    "zan": "赞暂攒昝簪",
    "zang": "脏葬藏奘驵",
    "zao": "造早燥糟遭灶藻藻蚤枣凿噪",
    "ze": "则择责泽测啧仄",
    "zei": "贼",
    "zen": "怎谮",
    "zeng": "增赠曾综缯甑",
    "zha": "查扎炸诈渣闸眨榨喳札吒",
    "zhai": "债柴窄摘宅侧砦翟寨",
    "zhan": "展战占站沾斩瞻粘盏崭湛詹旃谵",
    "zhang": "张长章掌涨障丈胀帐杖仗瘴蟑",
    "zhao": "照着找招朝召兆爪赵诏沼棹",
    "zhe": "这着者折浙遮哲辙蔗谪赭褶",
    "zhen": "真阵针振震镇珍侦贞斟枕枕疹鸩",
    "zheng": "政正争整证成征睁挣蒸症铮筝峥钲",
    "zhi": "之指制只支直治质至致职值识纸知置志止枝执智织址殖掷芝滞脂稚挚炙窒肢趾咫痔栉陟",
    "zhong": "中重终众种钟仲忠衷肿盅锺",
    "zhou": "周洲舟州咒昼宙轴肘骤皱诌啁",
    "zhu": "主著注住助诸筑竹珠逐朱柱祝猪蛛煮拄铸洙侏伫瘃",
    "zhua": "抓爪",
    "zhuai": "拽",
    "zhuan": "传专转砖撰赚篆馔啭",
    "zhuang": "状装庄壮撞妆桩僮庄",
    "zhui": "追坠缀锥赘骓",
    "zhun": "准谆窀",
    "zhuo": "著着捉桌拙浊卓灼酌啄琢濯擢",
    "zi": "自子资字姿滋紫咨仔渍滓姿孜姊龇缁",
    "zong": "总从宗踪纵综鬃粽",
    "zou": "走奏揍邹诹",
    "zu": "组族足祖阻卒诅俎镞",
    "zuan": "钻纂攥",
    "zui": "最罪嘴醉咀",
    "zun": "尊遵樽鳟",
    "zuo": "作做左座坐昨佐撮柞唑"
}

# 经典术数与文献专有词汇多音字消歧词典
COMPOUND_WORDS: Dict[str, str] = {
    # 易学与卦象
    "乾坤": "qian-kun",
    "乾造": "qian-zao",
    "坤造": "kun-zao",
    "乾元": "qian-yuan",
    "坤元": "kun-yuan",
    # 五行与干支
    "五行": "wu-xing",
    "行运": "xing-yun",
    "流行": "liu-xing",
    "天干": "tian-gan",
    "地支": "di-zhi",
    "纳音": "na-yin",
    "藏干": "cang-gan",
    "长生": "chang-sheng",
    "建禄": "jian-lu",
    "羊刃": "yang-ren",
    "魁罡": "kui-gang",
    "子平": "zi-ping",
    "相生": "xiang-sheng",
    "相克": "xiang-ke",
    "相刑": "xiang-xing",
    "相冲": "xiang-chong",
    "相害": "xiang-hai",
    "刑冲": "xing-chong",
    # 经典书名与篇名
    "三命通会": "san-ming-tong-hui",
    "渊海子平": "yuan-hai-zi-ping",
    "滴天髓": "di-tian-sui",
    "滴天髓阐微": "di-tian-sui-chan-wei",
    "子平真诠": "zi-ping-zhen-quan",
    "穷通宝鉴": "qiong-tong-bao-jian",
    "八字提要": "ba-zi-ti-yao",
    "神峰通考": "shen-feng-tong-kao",
    "星平会海": "xing-ping-hui-hai",
    "御定子平八字": "yu-ding-zi-ping-ba-zi",
    "兰台妙选": "lan-tai-miao-xuan",
    "玉照定真经": "yu-zhao-ding-zhen-jing",
    "壶中子": "hu-zhong-zi",
    "珞琭子": "luo-lu-zi",
    "千金赋": "qian-jin-fu",
    "金不换": "jin-bu-huan",
    "继善篇": "ji-shan-pian",
    "喜忌篇": "xi-ji-pian",
    "消息篇": "xiao-xi-pian",
    "通天论": "tong-tian-lun",
    # 历代名家
    "任铁樵": "ren-tie-qiao",
    "徐乐吾": "xu-le-wu",
    "沈孝瞻": "shen-xiao-zhan",
    "万民英": "wan-min-ying",
    "韦千里": "wei-qian-li",
    "袁树珊": "yuan-shu-shan",
    "张神峰": "zhang-shen-feng",
    "醉醒子": "zui-xing-zi",
}

# 中文数字字符集
CN_NUM_MAP = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9
}
CN_UNIT_MAP = {
    "十": 10, "百": 100, "千": 1000
}


class PinyinEngine:
    def __init__(self, config_path: Optional[Path] = None):
        self.char_map: Dict[str, str] = {}
        self.compound_words: Dict[str, str] = dict(COMPOUND_WORDS)
        self._build_char_map()

        # 加载自定义配置（若存在）
        self.load_config(config_path)

    def _build_char_map(self):
        """构建字符到拼音的单字倒排索引"""
        for syl, chars in SYLLABLE_MAP.items():
            for c in chars:
                if c not in self.char_map:
                    self.char_map[c] = syl

    def load_config(self, config_path: Optional[Path] = None):
        """加载自定义配置覆盖"""
        target = config_path or Path("classics_config.json")
        if target.exists():
            try:
                with open(target, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if "custom_pinyin" in cfg:
                        for k, v in cfg["custom_pinyin"].items():
                            self.char_map[k] = v
                    if "custom_words" in cfg:
                        for k, v in cfg["custom_words"].items():
                            self.compound_words[k] = v
            except Exception:
                pass

    def chinese_to_number(self, s: str) -> Optional[int]:
        """
        将中文数字转为整数（支持 0 到 999）：
        如 "一" -> 1, "十二" -> 12, "二十三" -> 23, "一百零五" -> 105
        """
        s = s.strip()
        if not s:
            return None
        if s.isdigit():
            return int(s)

        # 简单个位数
        if len(s) == 1 and s in CN_NUM_MAP:
            return CN_NUM_MAP[s]

        # 十几的情况（如 "十一", "十二"）
        if s.startswith("十"):
            if len(s) == 1:
                return 10
            elif len(s) == 2 and s[1] in CN_NUM_MAP:
                return 10 + CN_NUM_MAP[s[1]]

        total = 0
        current_num = 0

        for char in s:
            if char in CN_NUM_MAP:
                current_num = CN_NUM_MAP[char]
            elif char in CN_UNIT_MAP:
                unit = CN_UNIT_MAP[char]
                if current_num == 0:
                    current_num = 1
                total += current_num * unit
                current_num = 0
            else:
                return None

        total += current_num
        return total

    def to_slug(self, text: str) -> str:
        """
        将中文文本转换为优雅规范的 URL Slug：
        - 剥离书名号《》、〈〉
        - 特殊处理卷数：卷一 -> juan-01, 卷十二 -> juan-12, 卷一百 -> juan-100
        - 优先匹配专有复合词
        - 单字查表转换
        - 规范连字符并剔除噪音
        """
        text = re.sub(r'^[《〈](.*?)[》〉]$', r'\1', text.strip())

        # 1. 卷数匹配: 卷一、卷二... 卷[0-9]+
        m_juan = re.match(r'^卷([一二三四五六七八九十百0-9]+)$', text)
        if m_juan:
            num_val = self.chinese_to_number(m_juan.group(1))
            if num_val is not None:
                return f"juan-{num_val:02d}"

        # 2. 章节前缀匹配: 第X章, 第X卷
        m_chap = re.match(r'^第([一二三四五六七八九十百0-9]+)([卷篇章节论])$', text)
        if m_chap:
            num_val = self.chinese_to_number(m_chap.group(1))
            unit_char = m_chap.group(2)
            unit_pinyin = self.char_map.get(unit_char, "section")
            if num_val is not None:
                return f"di-{num_val:02d}-{unit_pinyin}"

        # 3. 复合词优先替换
        temp_text = text
        token_map = {}
        token_idx = 0

        # 按复合词长度倒序排列，优先长词匹配
        sorted_compounds = sorted(self.compound_words.keys(), key=len, reverse=True)
        for compound in sorted_compounds:
            if compound in temp_text:
                placeholder = "__TOKEN" + str(token_idx) + "__"
                token_map[placeholder] = self.compound_words[compound]
                temp_text = temp_text.replace(compound, " " + placeholder + " ")
                token_idx += 1

        # 4. 逐字拆解
        slug_parts = []
        tokens = temp_text.split()
        for tok in tokens:
            if tok in token_map:
                slug_parts.append(token_map[tok])
            else:
                for char in tok:
                    if char in self.char_map:
                        slug_parts.append(self.char_map[char])
                    elif re.match(r'[a-zA-Z0-9]', char):
                        slug_parts.append(char.lower())
                    elif re.match(r'[一-龥]', char):
                        # 生僻字 fallback: c + unicode hex
                        slug_parts.append(f"c{ord(char):x}")
                    elif char in [' ', '-', '_']:
                        slug_parts.append('-')

        slug = '-'.join(p.strip('-') for p in slug_parts if p.strip('-'))
        slug = re.sub(r'-+', '-', slug).strip('-')
        return slug if slug else "section"


# 全局单例引擎
DEFAULT_ENGINE = PinyinEngine()


def to_pinyin_slug(text: str) -> str:
    """快捷入口：转换为规范 Slug"""
    return DEFAULT_ENGINE.to_slug(text)


def chinese_to_number(s: str) -> Optional[int]:
    """快捷入口：中文数字转整数"""
    return DEFAULT_ENGINE.chinese_to_number(s)


if __name__ == "__main__":
    test_cases = [
        "三命通会",
        "卷一",
        "卷十二",
        "卷二十三",
        "论五行生成",
        "论干支源流",
        "滴天髓阐微",
        "八字提要",
        "穷通宝鉴",
        "神峰通考",
        "星平会海",
        "纳音取象",
        "寅月",
        "甲日",
        "乾坤",
        "徐乐吾",
        "任铁樵",
        "沈孝瞻",
    ]
    print("=" * 60)
    print("汉字拼音 Slug 引擎测试:")
    print("=" * 60)
    for tc in test_cases:
        print(f"{tc:15} -> {to_pinyin_slug(tc)}")
    print("=" * 60)
