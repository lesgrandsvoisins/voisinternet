for i in `cat ./images.txt`
  do echo $i
  dir=`dirname $i`
  base=`basename $i`
  wget -x https://blog.lesgrandsvoisins.com/content/$i
done