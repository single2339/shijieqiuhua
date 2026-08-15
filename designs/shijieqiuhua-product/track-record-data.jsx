// track-record-data.jsx — mock "sample sufficient" track-record dataset for the
// landing page proof section redesign. Numbers are illustrative placeholders
// for a future state where settled >= 20 (production is not there yet).

const TRACK_RECORD = {
  settled: 124,
  leanAccuracy: 0.68,
  scorelineAccuracy: 0.21,
  windowLabel: "近 124 场已结算判断",
  // rolling lean-accuracy %, oldest → newest, sparse weekly samples
  trend: [58, 60, 57, 61, 63, 62, 65, 64, 66, 68, 67, 69, 68],
  recent: [
    { league: "英超", date: "06-15", home: "曼城", away: "利物浦", lean: "主胜", band: "2-1 / 1-1", actualHome: 2, actualAway: 1, hit: true },
    { league: "欧冠", date: "06-12", home: "拜仁", away: "皇马", lean: "主负", band: "1-2 / 0-2", actualHome: 1, actualAway: 1, hit: false },
    { league: "世界杯", date: "06-10", home: "巴西", away: "阿根廷", lean: "主胜", band: "2-1 / 1-0", actualHome: 2, actualAway: 0, hit: true },
    { league: "英超", date: "06-08", home: "阿森纳", away: "切尔西", lean: "主胜", band: "1-0 / 2-0", actualHome: 1, actualAway: 0, hit: true },
    { league: "西甲", date: "06-05", home: "巴萨", away: "马竞", lean: "主负", band: "1-2 / 0-1", actualHome: 0, actualAway: 1, hit: true },
    { league: "英超", date: "06-02", home: "纽卡", away: "热刺", lean: "主胜", band: "2-1 / 1-1", actualHome: 1, actualAway: 1, hit: false },
    { league: "意甲", date: "05-29", home: "国米", away: "尤文", lean: "主胜", band: "1-0 / 2-1", actualHome: 2, actualAway: 1, hit: true },
    { league: "英超", date: "05-26", home: "曼联", away: "布莱顿", lean: "主胜", band: "2-0 / 1-0", actualHome: 2, actualAway: 0, hit: true },
  ],
};

Object.assign(window, { TRACK_RECORD });
