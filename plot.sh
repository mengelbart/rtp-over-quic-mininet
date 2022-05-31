set -x

for i in {0..8} ;
do 
	if [ -d "data/$i/" ]
	then
		./plot.py --capacity data/$i/capacity.log --rtp-received data/$i/receiver_rtp.log --rtp-sent data/$i/sender_rtp.log --cc data/$i/cc.log --rtcp-received data/$i/sender_rtcp.log --rtcp-sent data/$i/receiver_rtcp.log --config data/$i/config.json -o $i\_rates.png;
		./plot.py --qdelay data/$i/cc.log -o $i\_qdelay.png;
		./plot.py --loss data/$i/sender_rtp.log data/$i/receiver_rtp.log --config data/$i/config.json -o $i\_loss.png
		./plot.py --latency data/$i/sender_rtp.log data/$i/receiver_rtp.log --config data/$i/config.json -o $i\_latency.png
	fi
done

#for i in {0..5} ; do ./plot.py --rtp-received data/$i/receiver_rtp.log --rtp-sent data/$i/sender_rtp.log --cc data/$i/cc.log -o $i\_rates.png; done

