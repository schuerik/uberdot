alias s='echo "Hello" >> '
function t(){
echo "$2" >> $1
}


cd /home/god/repos/uberdot/test/regression/environment-event
t test.file $(cat name4)