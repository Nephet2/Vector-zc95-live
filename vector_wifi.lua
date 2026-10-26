-- Vector WiFi v1: staged four-channel commands, committed as a frame.
Config = {name="Vector WiFi v1", loop_freq_hz=100, menu_items={}}
local values = {}
for ch=1,4 do
 local base=(ch-1)*3
 values[ch]={0,80,100}
 local names={"Power ","Hz ","Width "}
 local maxes={1000,255,255}
 local mins={0,1,1}
 for k=1,3 do
  table.insert(Config.menu_items,{type="MIN_MAX",title=names[k]..ch,id=base+k,group=ch,min=mins[k],max=maxes[k],increment_step=1,default=values[ch][k],uom=""})
 end
end
table.insert(Config.menu_items,{type="MIN_MAX",title="Frame commit",id=13,min=0,max=1000,increment_step=1,default=0,uom=""})
local now_ms=0
local last_frame=-10000
local started=false
function Zero()
 started=false
 for ch=1,4 do zc.ChannelOff(ch); zc.SetPower(ch,0) end
end
function Setup()
 Zero()
end
function MinMaxChange(id,v)
 if id==13 then
  if v==0 then Zero(); last_frame=-10000; return end
  last_frame=now_ms
  started=true
  for ch=1,4 do
   local a=values[ch]
   zc.SetFrequency(ch,a[2]); zc.SetPulseWidth(ch,a[3],a[3]); zc.SetPower(ch,a[1])
   if a[1]>0 then zc.ChannelOn(ch) else zc.ChannelOff(ch) end
  end
 else
  local ch=math.floor((id-1)/3)+1
  local k=(id-1)%3+1
  if ch>=1 and ch<=4 then values[ch][k]=v end
 end
end
function Loop(time_ms)
 now_ms=time_ms
 if started and now_ms-last_frame>1500 then Zero() end
end
